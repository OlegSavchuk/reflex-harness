import math

from sprites.animation import half_turn_at
from sprites.physics import spin


def test_spin():
    assert spin((1.0, 0.0), math.pi, 0.5) == (0.0, 1.0)


def test_half_turn_at_end():
    assert half_turn_at((0.0, 1.0), 1.0) == (-0.0, -1.0)
