"""Receipts."""
from transit.fares import fare


def receipt_line(origin: str, dest: str, age: int) -> str:
    return f"{origin} -> {dest}: {fare(origin, dest, age) / 100:.2f}"
