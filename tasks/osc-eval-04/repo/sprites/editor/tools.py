"""Editor tools. The rotate handle reports its angle in degrees."""
from sprites.geometry.transform import rotate


def rotate_handle(point: tuple[float, float], degrees: float) -> tuple[float, float]:
    return rotate(point, degrees)
