"""Renewal reminders."""
from datetime import date, timedelta

from plans.renewals import renewal_dates


def reminder_dates(start: date, every_months: int, count: int, days_before: int = 3) -> list[date]:
    return [d - timedelta(days=days_before) for d in renewal_dates(start, every_months, count)]
