"""CSS color(srgb r g b) values are floats in 0.0-1.0, and results stay in that space."""
from palette.core.mix import blend


def mix_css(c1: tuple[float, float, float], c2: tuple[float, float, float], t: float) -> tuple[float, float, float]:
    return blend(c1, c2, t)
