"""SQLite-backed store for scheduled tasks."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ScheduledTask:
    id: int
    name: str
    cron_expr: str
    skill: str
    args: Dict[str, Any]
    notify_telegram_chat_id: Optional[int]
    enabled: bool
    created_at: float
    last_run_at: Optional[float]
    last_result: Optional[str]
    run_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "cron_expr": self.cron_expr,
            "skill": self.skill,
            "args": self.args,
            "notify_telegram_chat_id": self.notify_telegram_chat_id,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "last_run_at": self.last_run_at,
            "last_result": self.last_result,
            "run_count": self.run_count,
        }


class SchedulerStore:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                name                    TEXT NOT NULL,
                cron_expr               TEXT NOT NULL,
                skill                   TEXT NOT NULL,
                args_json               TEXT NOT NULL DEFAULT '{}',
                notify_telegram_chat_id INTEGER,
                enabled                 INTEGER NOT NULL DEFAULT 1,
                created_at              REAL NOT NULL,
                last_run_at             REAL,
                last_result             TEXT,
                run_count               INTEGER NOT NULL DEFAULT 0
            )
        """)
        self.conn.commit()

    def _row_to_task(self, row: sqlite3.Row) -> ScheduledTask:
        return ScheduledTask(
            id=row["id"],
            name=row["name"],
            cron_expr=row["cron_expr"],
            skill=row["skill"],
            args=json.loads(row["args_json"]),
            notify_telegram_chat_id=row["notify_telegram_chat_id"],
            enabled=bool(row["enabled"]),
            created_at=row["created_at"],
            last_run_at=row["last_run_at"],
            last_result=row["last_result"],
            run_count=row["run_count"],
        )

    def create(self, name: str, cron_expr: str, skill: str,
               args: Dict[str, Any] | None = None,
               notify_telegram_chat_id: int | None = None) -> ScheduledTask:
        now = time.time()
        cur = self.conn.execute(
            """INSERT INTO scheduled_tasks
               (name, cron_expr, skill, args_json, notify_telegram_chat_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, cron_expr, skill, json.dumps(args or {}, ensure_ascii=False),
             notify_telegram_chat_id, now),
        )
        self.conn.commit()
        return self.get(cur.lastrowid)

    def get(self, task_id: int) -> ScheduledTask | None:
        row = self.conn.execute(
            "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return self._row_to_task(row) if row else None

    def list_enabled(self) -> List[ScheduledTask]:
        rows = self.conn.execute(
            "SELECT * FROM scheduled_tasks WHERE enabled = 1 ORDER BY id"
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def list_all(self) -> List[ScheduledTask]:
        rows = self.conn.execute(
            "SELECT * FROM scheduled_tasks ORDER BY id"
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def update_last_run(self, task_id: int, result: str) -> None:
        self.conn.execute(
            """UPDATE scheduled_tasks
               SET last_run_at = ?, last_result = ?, run_count = run_count + 1
               WHERE id = ?""",
            (time.time(), result[:4000], task_id),
        )
        self.conn.commit()

    def set_enabled(self, task_id: int, enabled: bool) -> bool:
        cur = self.conn.execute(
            "UPDATE scheduled_tasks SET enabled = ? WHERE id = ?",
            (int(enabled), task_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def delete(self, task_id: int) -> bool:
        cur = self.conn.execute(
            "DELETE FROM scheduled_tasks WHERE id = ?", (task_id,)
        )
        self.conn.commit()
        return cur.rowcount > 0
