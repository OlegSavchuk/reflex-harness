"""Shipping data types."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Parcel:
    weight_kg: float
    country: str
    insured: bool = False
