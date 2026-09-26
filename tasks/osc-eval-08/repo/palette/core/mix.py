"""Colour blending shared by themes, gradients and the CSS importer."""


def blend(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    """Blend two 8-bit RGB colours (ints 0-255); t=0 gives c1, t=1 gives c2."""
    for c in (c1, c2):
        if len(c) != 3 or not all(isinstance(v, int) and 0 <= v <= 255 for v in c):
            raise TypeError(f"colours must be three ints in 0-255, got {c!r}")
    if not 0 <= t <= 1:
        raise ValueError(f"t must be in [0, 1], got {t}")
    return tuple(round(a + (b - a) * t) for a, b in zip(c1, c2))
