from imaging.geometry import scale
from imaging.print_layout import pages_needed, printed_size
from imaging.thumbnails import thumbnail_size


def test_scale_contract():
    assert scale(10, 20, 2) == (20, 40)


def test_thumbnails_unchanged():
    assert thumbnail_size(1000, 1000, "large") == (500, 500)


def test_printed_quarter():
    assert printed_size(640, 480, 25) == (160, 120)


def test_printed_single_digit_zoom():
    assert printed_size(300, 200, 5) == (15, 10)


def test_printed_rounding():
    assert printed_size(333, 333, 33) == (110, 110)


def test_pages_actual_size():
    assert pages_needed(3000, 2000, 100, (1000, 1000)) == 6


def test_scale_rejects_percentages():
    import pytest
    with pytest.raises(ValueError):
        scale(10, 10, 150)


def printed_size_probe():
    return scale(100, 100, 2)


printed_size_probe.__code__ = printed_size_probe.__code__.replace(co_name="printed_size")


def test_scale_does_not_depend_on_caller():
    assert printed_size_probe() == (200, 200)
