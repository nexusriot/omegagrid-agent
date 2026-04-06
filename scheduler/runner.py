"""Background scheduler that runs tasks on cron schedule."""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

import requests

from scheduler.store import SchedulerStore, ScheduledTask

logger = logging.getLogger(__name__)


def _cron_matches(cron_expr: str, dt: datetime) -> bool:
    """Check if a datetime matches a 5-field cron expression.

    Fields: minute hour day_of_month month day_of_week
    Supports: *, */N, N, N-M, comma-separated values.
    """
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return False

    values = [
        dt.minute,
        dt.hour,
        dt.day,
        dt.month,
        dt.isoweekday() % 7,  # 0=Sun, 1=Mon, ..., 6=Sat
    ]
    ranges = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]

    for field_str, val, (lo, hi) in zip(parts, values, ranges):
        if not _field_matches(field_str, val, lo, hi):
            return False
    return True


def _field_matches(field_str: str, value: int, lo: int, hi: int) -> bool:
    """Check if a single cron field matches a value."""
    for part in field_str.split(","):
        part = part.strip()
        step = 1
        if "/" in part:
            part, step_s = part.split("/", 1)
            step = int(step_s)

        if part == "*":
            if (value - lo) % step == 0:
                return True
        elif "-" in part:
            a, b = part.split("-", 1)
            a, b = int(a), int(b)
            if a <= value <= b and (value - a) % step == 0:
                return True
        else:
            if int(part) == value:
                return True
    return False


def _send_telegram(bot_token: str, chat_id: int, text: str) -> bool:
    """Send a message to a Telegram chat."""
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4096]},
            timeout=15,
        )
        if r.status_code != 200:
            logger.error("Telegram send failed: %s %s", r.status_code, r.text[:200])
            return False
        return True
    except Exception as e:
        logger.error("Telegram send error: %s", e)
        return False


class SchedulerRunner:
    """Background thread that checks and runs scheduled tasks every 60 seconds."""

    def __init__(self, store: SchedulerStore, skill_executor: Callable,
                 bot_token: str = "", check_interval: int = 60):
        self.store = store
        self.skill_executor = skill_executor
        self.bot_token = bot_token
        self.check_interval = check_interval
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="scheduler")
        self._thread.start()
        logger.info("Scheduler started (interval=%ds)", self.check_interval)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Scheduler stopped")

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.exception("Scheduler tick error: %s", e)
            self._stop_event.wait(self.check_interval)

    def _tick(self) -> None:
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        tasks = self.store.list_enabled()

        for task in tasks:
            if not _cron_matches(task.cron_expr, now):
                continue

            # Avoid double-run within the same minute
            if task.last_run_at:
                last = datetime.fromtimestamp(task.last_run_at, tz=timezone.utc)
                last = last.replace(second=0, microsecond=0)
                if last >= now:
                    continue

            self._run_task(task)

    def _run_task(self, task: ScheduledTask) -> None:
        logger.info("Scheduler running task #%d '%s': %s(%s)",
                     task.id, task.name, task.skill, task.args)
        try:
            result = self.skill_executor(task.skill, task.args)
            result_str = json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            result_str = json.dumps({"error": str(e)})
            logger.error("Task #%d failed: %s", task.id, e)

        self.store.update_last_run(task.id, result_str)
        logger.info("Task #%d result: %s", task.id, result_str[:200])

        # Push to Telegram if configured
        if task.notify_telegram_chat_id and self.bot_token:
            msg = f"⏰ Scheduled: {task.name}\n\n{result_str[:3900]}"
            _send_telegram(self.bot_token, task.notify_telegram_chat_id, msg)
