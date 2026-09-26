"""Tenancy invoices."""
from datetime import date

from lettings.calc.proration import prorate

DEPOSIT_CAP_CENTS = 150_000


def first_invoice(move_in: date, monthly_rent_cents: int) -> int:
    """First invoice in cents: the move-in month's rent prorated from the move-in day, plus a
    deposit of one month's rent capped at DEPOSIT_CAP_CENTS."""
    return prorate(monthly_rent_cents, move_in) + monthly_rent_cents
