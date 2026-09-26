"""CSS rgb() colours written as percentages: one int 0-100 per channel. Results stay in percentages."""
from swatch.core.mix import blend


def mix_css(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return blend(c1, c2, t)
