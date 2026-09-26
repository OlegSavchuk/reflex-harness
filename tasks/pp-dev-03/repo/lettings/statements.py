"""Tenant statements."""
from datetime import date

from lettings.rent import first_invoice


def welcome_statement(tenant: str, move_in: date, monthly_rent_cents: int) -> str:
    return f"{tenant}: first invoice {first_invoice(move_in, monthly_rent_cents) / 100:.2f}"
