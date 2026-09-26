"""Warehouse locations."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    code: str  # "<aisle>-<shelf>", e.g. "12-3"

    def walk_key(self) -> tuple[int, int]:
        """Sort key for a picking walk: aisle number, then shelf number."""
        aisle, shelf = self.code.split("-")
        return (aisle, shelf)
