from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from skills.base import BaseSkill

_FIELD_NAMES = ["minute", "hour", "day_of_month", "month", "day_of_week"]
_FIELD_RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
_MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_DOW_NAMES = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}


class CronScheduleSkill(BaseSkill):
    """Parse a cron expression, explain it in plain English, and show the next N run times."""

    name = "cron_schedule"
    description = "Parse a cron expression (5 fields), explain it, and calculate the next run times."
    parameters = {
        "expression": {"type": "string", "description": "Cron expression (5 fields), e.g. '*/15 * * * *'", "required": True},
        "count": {"type": "number", "description": "Number of next runs to show (default 5, max 20)", "required": False},
    }

    def execute(self, expression: str, count: int = 5, **kwargs) -> Dict[str, Any]:
        count = min(max(int(count), 1), 20)
        expr = expression.strip()
        parts = expr.split()
        if len(parts) != 5:
            return {"error": f"Expected 5 fields, got {len(parts)}. Format: minute hour day month weekday"}

        try:
            parsed = [_parse_field(parts[i], i) for i in range(5)]
        except ValueError as e:
            return {"error": str(e)}

        explanation = _explain(parts)
        next_runs = _next_runs(parsed, count)

        return {
            "expression": expr,
            "explanation": explanation,
            "fields": {_FIELD_NAMES[i]: parts[i] for i in range(5)},
            "next_runs": [dt.isoformat() for dt in next_runs],
        }


def _parse_field(field: str, idx: int) -> set[int]:
    """Parse a single cron field into a set of valid integer values."""
    lo, hi = _FIELD_RANGES[idx]
    values = set()

    for part in field.split(","):
        part = part.strip().lower()

        # Replace named months/days
        if idx == 3:
            for name, num in _MONTH_NAMES.items():
                part = part.replace(name, str(num))
        elif idx == 4:
            for name, num in _DOW_NAMES.items():
                part = part.replace(name, str(num))

        # Handle step: */2, 1-5/2
        step = 1
        if "/" in part:
            part, step_str = part.split("/", 1)
            step = int(step_str)

        if part == "*":
            values.update(range(lo, hi + 1, step))
        elif "-" in part:
            a, b = part.split("-", 1)
            a, b = int(a), int(b)
            values.update(range(a, b + 1, step))
        else:
            values.add(int(part))

    if not values:
        raise ValueError(f"Field '{field}' produced no valid values")
    for v in values:
        if v < lo or v > hi:
            raise ValueError(f"Value {v} out of range [{lo}-{hi}] for {_FIELD_NAMES[idx]}")
    return values


def _explain(parts: List[str]) -> str:
    """Generate a human-readable explanation of the cron expression."""
    minute, hour, dom, month, dow = parts

    pieces = []

    if minute == "*":
        pieces.append("every minute")
    elif minute.startswith("*/"):
        pieces.append(f"every {minute[2:]} minutes")
    elif "," in minute:
        pieces.append(f"at minutes {minute}")
    else:
        pieces.append(f"at minute {minute}")

    if hour == "*":
        pieces.append("of every hour")
    elif hour.startswith("*/"):
        pieces.append(f"every {hour[2:]} hours")
    else:
        pieces.append(f"at hour {hour}")

    if dom != "*":
        pieces.append(f"on day {dom} of the month")
    if month != "*":
        pieces.append(f"in month {month}")
    if dow != "*":
        day_map = {
            "0": "Sunday", "1": "Monday", "2": "Tuesday", "3": "Wednesday",
            "4": "Thursday", "5": "Friday", "6": "Saturday",
        }
        days = [day_map.get(d.strip(), d.strip()) for d in dow.split(",")]
        pieces.append(f"on {', '.join(days)}")

    return ", ".join(pieces)


def _next_runs(parsed: List[set[int]], count: int) -> List[datetime]:
    """Calculate the next N run times from now (UTC)."""
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    dt = now + timedelta(minutes=1)
    results: List[datetime] = []

    # Scan up to 2 years of minutes (but short-circuit with day skipping)
    limit = 366 * 24 * 60
    checked = 0
    while len(results) < count and checked < limit:
        dow = dt.isoweekday() % 7  # Monday=1..Sunday=7 -> 0=Sun,1=Mon,...,6=Sat
        if (dt.minute in parsed[0] and
                dt.hour in parsed[1] and
                dt.day in parsed[2] and
                dt.month in parsed[3] and
                dow in parsed[4]):
            results.append(dt)
            dt += timedelta(minutes=1)
        else:
            dt += timedelta(minutes=1)
        checked += 1

    return results
