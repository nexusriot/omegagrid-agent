---
name: uk_bank_holiday
description: Check if today (or a given date) is a UK bank holiday
parameters:
  date:
    type: string
    description: "Date to check in YYYY-MM-DD format (optional, defaults to today)"
    required: false
  region:
    type: string
    description: "UK region: england-and-wales, scotland, or northern-ireland (default: england-and-wales)"
    required: false
steps:
  - name: get_date
    skill: datetime
  - name: get_holidays
    endpoint: https://www.gov.uk/bank-holidays.json
    method: GET
---

Step results:
- `get_date` returns {date, time, day_of_week, iso, unix_timestamp} from the local datetime skill.
- `get_holidays` returns the UK bank holidays JSON keyed by region.

Logic:
1. Use the user-supplied `date` parameter if present, otherwise use `get_date.date`
   (already in YYYY-MM-DD format).
2. From `get_holidays`, look up the region key (default `england-and-wales`).
   Structure: `{"england-and-wales": {"events": [{"date": "YYYY-MM-DD", "title": "..."}]}}`.
3. Check whether the target date appears in that region's `events` list.
4. Report clearly:
   - Whether the date is a bank holiday.
   - If yes, which holiday it is (title).
   - The next upcoming bank holiday from the list.
