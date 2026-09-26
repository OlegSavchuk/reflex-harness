import pytest

from minefield.core.board import adjacent_mines
from minefield.play import _reveal, click, typed

BOARD = ["*.....", "..*...", "......", ".....*", "......", "*....."]


def test_typed_other_moves():
    assert [typed(BOARD, m) for m in ("B1", "F3", "A6", "C2")] == ['2', '1', 'boom', 'boom']


def test_click_unchanged():
    assert [click(BOARD, x, y) for x, y in ((24, 8), (40, 40), (80, 70))] == ['2', '1', '1']


def test_adjacent_counts():
    assert [adjacent_mines(BOARD, c, r) for c, r in ((1, 0), (4, 3), (0, 4))] == [2, 1, 1]


def test_off_board_still_rejected():
    with pytest.raises(IndexError):
        adjacent_mines(BOARD, 6, 0)


def typed_probe():
    return _reveal(BOARD, 1, 0)


typed_probe.__code__ = typed_probe.__code__.replace(co_name="typed")


def test_reveal_does_not_depend_on_caller():
    assert typed_probe() == '2'
