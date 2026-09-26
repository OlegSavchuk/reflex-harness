import pytest

from photokit.cli.manual import manual_crop
from photokit.ops.crop import crop_box
from photokit.smart_crop import center_crop


def test_manual_one_pixel():
    assert manual_crop(400, 300, (0, 0, 1, 1)) == (0, 0, 1, 1)


def test_manual_full_frame():
    assert manual_crop(640, 480, (0, 0, 640, 480)) == (0, 0, 640, 480)


def test_manual_offset():
    assert manual_crop(1000, 800, (250, 100, 750, 700)) == (250, 100, 750, 700)


def test_crop_still_rejects_unnormalized():
    with pytest.raises(ValueError):
        crop_box(100, 100, (0, 0, 2, 2))


def test_smart_unchanged():
    assert center_crop(200, 100, 1.0) == (0, 0, 200, 100)


def manual_crop_probe():
    return crop_box(100, 100, (0.1, 0.2, 0.5, 0.6))


manual_crop_probe.__code__ = manual_crop_probe.__code__.replace(co_name="manual_crop")


def test_crop_does_not_depend_on_caller():
    assert manual_crop_probe() == (10, 20, 50, 60)
