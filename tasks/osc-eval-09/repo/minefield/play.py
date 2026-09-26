"""Moves: mouse clicks give pixel positions; typed moves use a column letter and a 1-based
row number ("C2" = column C, row 2)."""
from minefield.core.board import adjacent_mines

CELL_PX = 16


def _reveal(board: list[str], col: int, row: int) -> str:
    if board[row][col] == "*":
        return "boom"
    return str(adjacent_mines(board, col, row))


def click(board: list[str], x_px: int, y_px: int) -> str:
    return _reveal(board, x_px // CELL_PX, y_px // CELL_PX)


def typed(board: list[str], move: str) -> str:
    col, row = ord(move[0].upper()) - ord("A"), int(move[1:]) - 1
    return _reveal(board, row, col)
