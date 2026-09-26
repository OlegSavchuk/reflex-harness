"""Dimension scaling shared by thumbnails and print layout."""


def scale(width: int, height: int, factor: float) -> tuple[int, int]:
    """Scale dimensions by a ratio (0.5 = half size). Rounds to whole pixels."""
    if not 0 < factor <= 10:
        raise ValueError(f"scale factor must be a ratio in (0, 10], got {factor}")
    return round(width * factor), round(height * factor)
