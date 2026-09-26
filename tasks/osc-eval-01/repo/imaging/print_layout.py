"""Print layout. Zoom levels come from the print dialog as percentages (100 = actual size)."""
from imaging.geometry import scale


def printed_size(width: int, height: int, zoom_percent: float) -> tuple[int, int]:
    return scale(width, height, zoom_percent)


def pages_needed(width: int, height: int, zoom_percent: float, page: tuple[int, int]) -> int:
    w, h = printed_size(width, height, zoom_percent)
    return -(-w // page[0]) * -(-h // page[1])
