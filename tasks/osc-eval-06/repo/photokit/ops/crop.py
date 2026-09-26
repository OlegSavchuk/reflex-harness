"""Crop-box conversion shared by smart crop and the manual crop tool."""


def crop_box(width: int, height: int, box: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    """Pixel box for a normalized box (x0, y0, x1, y1), each coordinate in [0, 1]."""
    x0, y0, x1, y1 = box
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError(f"box must be normalized with x0 < x1 and y0 < y1, got {box}")
    return (round(x0 * width), round(y0 * height), round(x1 * width), round(y1 * height))
