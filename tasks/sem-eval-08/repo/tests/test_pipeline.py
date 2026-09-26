from signalkit.pipeline import smooth
from signalkit.plots import sparkline_points


def test_smooth_pairs():
    assert smooth([1, 2, 3, 4, 5], 2) == [1.5, 2.5, 3.5, 4.5]


def test_sparkline():
    assert sparkline_points([10, 20, 30]) == [15, 25]


def test_short_series_unchanged():
    assert smooth([1], 3) == [1]
