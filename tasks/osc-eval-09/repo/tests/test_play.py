from minefield.play import click, typed

BOARD = ["**...", ".....", "....*", ".*...", "....."]


def test_typed_counts_neighbours():
    assert typed(BOARD, "D1") == '0'


def test_typed_mine():
    assert typed(BOARD, "E3") == "boom"


def test_click_counts_neighbours():
    assert click(BOARD, 40, 8) == '1'


def test_click_mine():
    assert click(BOARD, 20, 50) == "boom"
