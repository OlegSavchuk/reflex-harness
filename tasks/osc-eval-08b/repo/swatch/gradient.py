"""Gradients (8-bit colours)."""
from swatch.core.mix import blend


def stops(c1: tuple[int, int, int], c2: tuple[int, int, int], n: int) -> list[tuple[int, int, int]]:
    return [blend(c1, c2, i / (n - 1)) for i in range(n)]
