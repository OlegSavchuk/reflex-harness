"""Colour blending shared by themes, gradients and the CSS importer."""


def _to_linear(v: int) -> float:
    c = v / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _to_srgb(x: float) -> int:
    c = 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055
    return round(c * 255)


def blend(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    """Blend two 8-bit sRGB colours (ints 0-255) in linear light; t=0 gives c1, t=1 gives c2."""
    for c in (c1, c2):
        if len(c) != 3 or not all(isinstance(v, int) and 0 <= v <= 255 for v in c):
            raise TypeError(f"colours must be three ints in 0-255, got {c!r}")
    if not 0 <= t <= 1:
        raise ValueError(f"t must be in [0, 1], got {t}")
    return tuple(_to_srgb(_to_linear(a) + (_to_linear(b) - _to_linear(a)) * t) for a, b in zip(c1, c2))
