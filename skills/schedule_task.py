from __future__ import annotations

from typing import Any, Dict

from skills.base import BaseSkill


class ScheduleTaskSkill(BaseSkill):
    """Create, list, or delete scheduled tasks that run on a cron schedule."""

    name = "schedule_task"
    description = (
        "Manage scheduled tasks. Actions: "
        "'create' a new recurring task (runs a skill on cron schedule, optionally notifies Telegram), "
        "'list' all scheduled tasks, "
        "'delete' a task by id, "
        "'enable'/'disable' a task by id."
    )
    parameters = {
        "action": {
            "type": "string",
            "description": "Action: create, list, delete, enable, disable",
            "required": True,
        },
        "name": {
            "type": "string",
            "description": "Task name (for create)",
            "required": False,
        },
        "cron_expr": {
            "type": "string",
            "description": "Cron expression, e.g. '*/5 * * * *' (for create)",
            "required": False,
        },
        "skill": {
            "type": "string",
            "description": "Skill to run, e.g. 'ping_check', 'weather' (for create)",
            "required": False,
        },
        "args": {
            "type": "object",
            "description": "Arguments for the skill, e.g. {\"host\": \"example.com\"} (for create)",
            "required": False,
        },
        "notify_telegram_chat_id": {
            "type": "number",
            "description": "Telegram chat ID to send results to (for create). Use the current chat_id if user asks for Telegram notifications.",
            "required": False,
        },
        "task_id": {
            "type": "number",
            "description": "Task ID (for delete/enable/disable)",
            "required": False,
        },
    }

    def __init__(self, scheduler_store):
        self._store = scheduler_store

    def execute(self, action: str = "list", **kwargs) -> Dict[str, Any]:
        action = action.lower().strip()

        if action == "create":
            return self._create(**kwargs)
        elif action == "list":
            return self._list()
        elif action == "delete":
            return self._delete(**kwargs)
        elif action == "enable":
            return self._set_enabled(True, **kwargs)
        elif action == "disable":
            return self._set_enabled(False, **kwargs)
        else:
            return {"error": f"Unknown action: {action}. Use: create, list, delete, enable, disable"}

    def _create(self, name: str = "", cron_expr: str = "", skill: str = "",
                args: dict = None, notify_telegram_chat_id: int = None, **kw) -> Dict[str, Any]:
        if not cron_expr:
            return {"error": "cron_expr is required (e.g. '*/5 * * * *')"}
        if not skill:
            return {"error": "skill is required (e.g. 'ping_check', 'weather')"}
        if not name:
            name = f"{skill} ({cron_expr})"

        task = self._store.create(
            name=name,
            cron_expr=cron_expr,
            skill=skill,
            args=args or {},
            notify_telegram_chat_id=int(notify_telegram_chat_id) if notify_telegram_chat_id else None,
        )
        return {
            "created": True,
            "task": task.to_dict(),
        }

    def _list(self) -> Dict[str, Any]:
        tasks = self._store.list_all()
        return {
            "count": len(tasks),
            "tasks": [t.to_dict() for t in tasks],
        }

    def _delete(self, task_id: int = None, **kw) -> Dict[str, Any]:
        if task_id is None:
            return {"error": "task_id is required"}
        if self._store.delete(int(task_id)):
            return {"deleted": True, "task_id": int(task_id)}
        return {"error": f"Task {task_id} not found"}

    def _set_enabled(self, enabled: bool, task_id: int = None, **kw) -> Dict[str, Any]:
        if task_id is None:
            return {"error": "task_id is required"}
        if self._store.set_enabled(int(task_id), enabled):
            return {"ok": True, "task_id": int(task_id), "enabled": enabled}
        return {"error": f"Task {task_id} not found"}
