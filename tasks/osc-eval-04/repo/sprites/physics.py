"""Physics step. Angular velocity is in radians per second."""
from sprites.geometry.transform import rotate


def spin(point: tuple[float, float], omega: float, dt: float) -> tuple[float, float]:
    return rotate(point, omega * dt)
