"""Themes (8-bit colours)."""
from palette.core.mix import blend


def accent(base: tuple[int, int, int], highlight: tuple[int, int, int]) -> tuple[int, int, int]:
    return blend(base, highlight, 0.25)
