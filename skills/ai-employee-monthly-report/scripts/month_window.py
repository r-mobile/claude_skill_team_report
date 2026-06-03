#!/usr/bin/env python3
"""Compute the Jira date window for a monthly employee report.

The report covers a whole calendar month: from the 1st (00:00) up to either
the last day of that month, or — if it is the current month — today
(inclusive). The script outputs the inclusive start date and an *exclusive*
upper bound, which is the cleanest way to express "the whole last day is
included" in Jira JQL (`updated >= START AND updated < END_EXCLUSIVE`).

Usage:
    python scripts/month_window.py "февраль"
    python scripts/month_window.py "март 2025"
    python scripts/month_window.py "прошлый месяц"
    python scripts/month_window.py "текущий месяц"
    python scripts/month_window.py 2          # month number
    python scripts/month_window.py            # defaults to current month

Output (JSON):
    {
      "month": 2,
      "year": 2026,
      "label": "февраль 2026",
      "start": "2026-02-01",          # inclusive lower bound
      "end_exclusive": "2026-03-01",  # exclusive upper bound for JQL
      "end_inclusive": "2026-02-28",  # last day actually covered (for display)
      "is_current_month": false
    }
"""

import calendar
import datetime
import json
import re
import sys

MONTHS = {
    "январь": 1, "января": 1, "янв": 1,
    "февраль": 2, "февраля": 2, "фев": 2,
    "март": 3, "марта": 3, "мар": 3,
    "апрель": 4, "апреля": 4, "апр": 4,
    "май": 5, "мая": 5,
    "июнь": 6, "июня": 6, "июн": 6,
    "июль": 7, "июля": 7, "июл": 7,
    "август": 8, "августа": 8, "авг": 8,
    "сентябрь": 9, "сентября": 9, "сен": 9, "сент": 9,
    "октябрь": 10, "октября": 10, "окт": 10,
    "ноябрь": 11, "ноября": 11, "ноя": 11, "нояб": 11,
    "декабрь": 12, "декабря": 12, "дек": 12,
}

MONTH_NAMES_NOM = {
    1: "январь", 2: "февраль", 3: "март", 4: "апрель", 5: "май", 6: "июнь",
    7: "июль", 8: "август", 9: "сентябрь", 10: "октябрь", 11: "ноябрь",
    12: "декабрь",
}


def resolve(spec: str, today: datetime.date):
    """Return (year, month) from a free-text month spec."""
    s = (spec or "").strip().lower()

    # No spec -> current month.
    if not s or s in ("текущий месяц", "этот месяц", "current", "this month"):
        return today.year, today.month

    if s in ("прошлый месяц", "предыдущий месяц", "last month", "previous month"):
        first = today.replace(day=1)
        prev = first - datetime.timedelta(days=1)
        return prev.year, prev.month

    # Explicit year anywhere in the string.
    year_match = re.search(r"(19|20)\d{2}", s)
    explicit_year = int(year_match.group()) if year_match else None

    # Month by name.
    month = None
    for name, num in MONTHS.items():
        if re.search(rf"\b{name}\b", s):
            month = num
            break

    # Month by number (e.g. "2", "02", "месяц 2"), avoiding the year digits.
    if month is None:
        candidate = s
        if year_match:
            candidate = candidate.replace(year_match.group(), " ")
        num_match = re.search(r"\b(0?[1-9]|1[0-2])\b", candidate)
        if num_match:
            month = int(num_match.group())

    if month is None:
        raise ValueError(f"Не удалось распознать месяц в запросе: {spec!r}")

    if explicit_year is not None:
        year = explicit_year
    else:
        # No year given: pick the most recent occurrence of this month that is
        # not in the future. If the named month is later than the current
        # month, it must mean last year.
        year = today.year
        if month > today.month:
            year -= 1

    return year, month


def main():
    spec = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    today = datetime.date.today()
    year, month = resolve(spec, today)

    start = datetime.date(year, month, 1)

    last_day = calendar.monthrange(year, month)[1]
    month_end = datetime.date(year, month, last_day)

    is_current = (year == today.year and month == today.month)
    if is_current:
        end_inclusive = today
        end_exclusive = today + datetime.timedelta(days=1)
    else:
        end_inclusive = month_end
        end_exclusive = month_end + datetime.timedelta(days=1)

    out = {
        "month": month,
        "year": year,
        "label": f"{MONTH_NAMES_NOM[month]} {year}",
        "start": start.isoformat(),
        "end_exclusive": end_exclusive.isoformat(),
        "end_inclusive": end_inclusive.isoformat(),
        "is_current_month": is_current,
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
