"""Thumbnails. Sizes are ratios of the original."""
from imaging.geometry import scale

PRESETS = {"small": 0.1, "medium": 0.25, "large": 0.5}


def thumbnail_size(width: int, height: int, preset: str = "medium") -> tuple[int, int]:
    return scale(width, height, PRESETS[preset])


def fits_within(size: tuple[int, int], box: tuple[int, int]) -> bool:
    return size[0] <= box[0] and size[1] <= box[1]
