"""Stock data types."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    sku: str
    qty: int
    min_level: int
    max_level: int
