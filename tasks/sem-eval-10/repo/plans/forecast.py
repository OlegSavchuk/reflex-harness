"""Renewal forecasts."""
from datetime import date

from plans.renewals import renewal_dates


def renewals_in_year(start: date, every_months: int, year: int) -> int:
    """How many renewals of a plan started on `start` fall in `year` (looks ten years ahead)."""
    return sum(d.year == year for d in renewal_dates(start, every_months, 120 // every_months))
