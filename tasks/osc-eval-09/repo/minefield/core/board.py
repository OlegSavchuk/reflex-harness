"""Board queries shared by every kind of move. A board is a list of equal-length rows; '*' is a mine."""


def adjacent_mines(board: list[str], col: int, row: int) -> int:
    """Mines in the (up to) eight cells around column `col` of row `row`, both 0-based."""
    if not (0 <= row < len(board) and 0 <= col < len(board[0])):
        raise IndexError(f"cell ({col}, {row}) is off the board")
    return sum(board[r][c] == "*"
               for r in range(max(0, row - 1), min(len(board), row + 2))
               for c in range(max(0, col - 1), min(len(board[0]), col + 2))
               if (r, c) != (row, col))
