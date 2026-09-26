"""Car loans. Rates are fractions."""
from lending.core.interest import monthly_payment


def car_payment(amount: float, rate: float, months: int = 60) -> float:
    return monthly_payment(amount, rate, months)
