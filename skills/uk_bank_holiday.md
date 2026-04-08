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
    endpoint: https://aisenseapi.com/services/v1/datetime
    method: GET
  - name: get_holidays
    endpoint: https://www.gov.uk/bank-holidays.json
    method: GET
---

After fetching the results from both steps:

1. Use the `date` parameter if provided, otherwise extract today's date from the
   get_date step result (look for a date field in ISO format, use YYYY-MM-DD).
2. From the get_holidays step result, look up the region key (default
   "england-and-wales"). The structure is:
   `{"england-and-wales": {"events": [{"date": "YYYY-MM-DD", "title": "..."}]}}`.
3. Check if the target date appears in that region's events list.
4. Report clearly:
   - Whether the date is a bank holiday.
   - If yes, which holiday it is (title).
   - The next upcoming bank holiday from the list.
