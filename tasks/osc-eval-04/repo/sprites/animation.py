"""Animation curves. Angles are radians."""
import math

from sprites.geometry.transform import rotate


def half_turn_at(point: tuple[float, float], progress: float) -> tuple[float, float]:
    return rotate(point, math.pi * progress)
