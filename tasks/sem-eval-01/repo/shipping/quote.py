"""Shipping quotes."""
from shipping.models import Parcel
from shipping.zones import rate_per_kg, zone_for

BASE_FEE = 3.0
INSURANCE_RATE = 0.02


def quote(parcel: Parcel, declared_value: float = 0.0) -> float:
    cost = BASE_FEE + parcel.weight_kg * rate_per_kg(zone_for(parcel.country))
    if parcel.insured:
        cost += declared_value * INSURANCE_RATE
    return round(cost, 2)
