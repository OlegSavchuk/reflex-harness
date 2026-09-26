import math

import pytest

from sprites.editor.tools import rotate_handle
from sprites.geometry.transform import rotate
from sprites.physics import spin


def test_small_editor_angle():
    assert rotate_handle((1.0, 0.0), 5) == (0.9962, 0.0872)


def test_negative_editor_angle():
    assert rotate_handle((0.0, 2.0), -3) == (0.1047, 1.9973)


def test_full_turn_editor():
    assert rotate_handle((1.5, -0.5), 360) == (1.5, -0.5)


def test_rotate_still_rejects_more_than_a_turn():
    with pytest.raises(ValueError):
        rotate((1.0, 0.0), 7.0)


def test_physics_unchanged():
    assert spin((0.0, 1.0), 1.0, 0.25) == (-0.2474, 0.9689)


def rotate_handle_probe():
    return rotate((1.0, 0.0), math.pi / 2)


rotate_handle_probe.__code__ = rotate_handle_probe.__code__.replace(co_name="rotate_handle")


def test_rotate_does_not_depend_on_caller():
    assert rotate_handle_probe() == (0.0, 1.0)


def test_integer_radians_are_radians():
    assert rotate((1.0, 0.0), 1) == (0.5403, 0.8415)
    assert rotate((0.0, 1.0), -2) == (0.9093, -0.4161)


def test_fractional_editor_angle():
    assert rotate_handle((1.0, 0.0), 30.0) == (0.866, 0.5)
    assert rotate_handle((2.0, 0.0), 22.5) == (1.8478, 0.7654)
