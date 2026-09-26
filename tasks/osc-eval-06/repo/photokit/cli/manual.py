"""Manual crop. The user drags a rectangle measured in pixels."""
from photokit.ops.crop import crop_box


def manual_crop(width: int, height: int, rect: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    return crop_box(width, height, rect)
