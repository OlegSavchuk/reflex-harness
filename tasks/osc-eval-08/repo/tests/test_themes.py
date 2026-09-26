from palette.gradient import stops
from palette.themes import accent


def test_accent():
    assert accent((0, 0, 0), (200, 100, 40)) == (50, 25, 10)


def test_stops():
    assert stops((0, 0, 0), (255, 255, 255), 3) == [(0, 0, 0), (128, 128, 128), (255, 255, 255)]
