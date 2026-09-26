from swatch.gradient import stops
from swatch.themes import accent


def test_accent():
    assert accent((0, 0, 0), (200, 100, 40)) == (106, 50, 16)


def test_stops():
    assert stops((0, 0, 0), (255, 255, 255), 3) == [(0, 0, 0), (188, 188, 188), (255, 255, 255)]
