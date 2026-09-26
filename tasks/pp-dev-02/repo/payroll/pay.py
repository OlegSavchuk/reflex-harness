"""Net pay."""
from payroll.tax import income_tax


def net_pay(hours: float, rate_cents: int) -> int:
    """Net weekly pay in cents: hours up to 40 at the hourly rate, hours above 40 at one and a
    half times the rate, minus income tax on the gross."""
    gross = round(min(hours, 40) * rate_cents + max(hours - 40, 0) * rate_cents)
    return gross - income_tax(gross)
