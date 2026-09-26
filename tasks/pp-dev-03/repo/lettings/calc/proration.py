"""Rent proration by calendar days."""
from datetime import date

# Days per month, January first; February gains a day in leap years.
_MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 31, 31, 30, 31]


def _days_in_month(d: date) -> int:
    leap = d.year % 4 == 0 and (d.year % 100 != 0 or d.year % 400 == 0)
    return _MONTH_DAYS[d.month - 1] + (1 if d.month == 2 and leap else 0)


def prorate(amount_cents: int, start: date) -> int:
    """The share of a monthly amount from `start` to the end of its month, both days included."""
    days = _days_in_month(start)
    return round(amount_cents * (days - start.day + 1) / days)
