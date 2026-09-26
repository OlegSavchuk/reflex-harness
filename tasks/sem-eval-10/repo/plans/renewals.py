"""Renewal schedules."""
from datetime import date

from plans.dates import add_months


def renewal_dates(start: date, every_months: int, count: int) -> list[date]:
    """The next `count` renewal dates of a plan billed every `every_months` months from `start`."""
    if every_months < 1:
        raise ValueError("every_months must be at least 1")
    return [add_months(start, every_months * k) for k in range(1, count + 1)]
