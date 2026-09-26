"""Calendar arithmetic."""
from datetime import date


def add_months(d: date, months: int) -> date:
    """The same day of the month `months` later; a day past the end of the target month becomes
    that month's last day (Jan 31 + 1 month = Feb 28, or Feb 29 in a leap year)."""
    y, m = divmod(d.month - 1 + months, 12)
    return date(d.year + y, m + 1, min(d.day, 28))
