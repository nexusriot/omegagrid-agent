from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from skills.base import BaseSkill


class DateTimeSkill(BaseSkill):
    """Returns the current date, time, and day of the week in UTC."""

    name = "datetime"
    description = "Get current date and time in UTC."
    parameters = {}

    def execute(self, **kwargs) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "day_of_week": now.strftime("%A"),
            "iso": now.isoformat(),
            "unix_timestamp": int(now.timestamp()),
        }
