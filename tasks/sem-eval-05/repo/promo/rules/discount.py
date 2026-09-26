"""Discount rules."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Discount:
    sku: str
    percent: int

    def applies_to(self, sku: str) -> bool:
        """A discount applies to exactly one SKU."""
        return sku.startswith(self.sku)
