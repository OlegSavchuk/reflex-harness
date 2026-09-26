"""2D rotation shared by physics, animation and the editor tools."""
import math


def rotate(point: tuple[float, float], angle: float) -> tuple[float, float]:
    """Rotate a point about the origin by `angle` radians (counter-clockwise)."""
    if abs(angle) > math.tau:
        raise ValueError(f"angle must be in radians within one turn, got {angle}")
    x, y = point
    c, s = math.cos(angle), math.sin(angle)
    return (round(x * c - y * s, 4), round(x * s + y * c, 4))
