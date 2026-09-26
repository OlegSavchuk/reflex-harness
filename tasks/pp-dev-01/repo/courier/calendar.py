"""Business-day calendar."""
from datetime import date

# Fixed-date company holidays as (month, day): New Year's Day (Jan 1), Founders' Day (Jun 12),
# Christmas Day (Dec 25) and Boxing Day (Dec 26).
HOLIDAYS = {(1, 1), (6, 21), (12, 25), (12, 26)}


def is_business_day(d: date) -> bool:
    """Monday to Friday, except company holidays."""
    return d.weekday() < 5 and (d.month, d.day) not in HOLIDAYS
