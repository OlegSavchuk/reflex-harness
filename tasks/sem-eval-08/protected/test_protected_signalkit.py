import pytest

from signalkit.filters.rolling import moving_average


def test_moving_average_window_three():
    assert moving_average([2, 4, 6, 8], 3) == [4.0, 6.0]


def test_window_of_one():
    assert moving_average([3, 5], 1) == [3.0, 5.0]


def test_rejects_zero_window():
    with pytest.raises(ValueError):
        moving_average([1, 2], 0)


def _ma(values, window):
    return moving_average(values, window)


def test_average_outside_a_test_function():
    assert _ma([1, 3], 2) == [2.0]
