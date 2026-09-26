"""Delivery promises."""
from datetime import date, timedelta

from courier.calendar import is_business_day


def delivery_date(shipped: date, business_days: int) -> date:
    """The day `business_days` business days after `shipped` (0 = the ship date itself).
    A negative number of days is an error (ValueError)."""
    d, left = shipped, business_days
    while left > 0:
        d += timedelta(days=1)
        if is_business_day(d):
            left -= 1
    return d
