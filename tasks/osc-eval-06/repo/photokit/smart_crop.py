"""Smart crop. The saliency model returns normalized boxes."""
from photokit.ops.crop import crop_box


def center_crop(width: int, height: int, fraction: float) -> tuple[int, int, int, int]:
    m = (1 - fraction) / 2
    return crop_box(width, height, (m, m, 1 - m, 1 - m))
