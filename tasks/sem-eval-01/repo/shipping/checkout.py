"""Checkout totals."""
from shipping.models import Parcel
from shipping.quote import quote


def checkout_total(parcels: list[Parcel], declared_value: float = 0.0) -> float:
    return round(sum(quote(p, declared_value) for p in parcels), 2)
