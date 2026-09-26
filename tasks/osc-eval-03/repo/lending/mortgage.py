"""Mortgages. Rates are fractions."""
from lending.core.interest import monthly_payment


def mortgage_payment(price: float, deposit: float, rate: float, years: int) -> float:
    return monthly_payment(price - deposit, rate, years * 12)
