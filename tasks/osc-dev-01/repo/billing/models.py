"""Billing data types."""
from dataclasses import dataclass


@dataclass(frozen=True)
class LineItem:
    description: str
    quantity: int
    unit_price: float
