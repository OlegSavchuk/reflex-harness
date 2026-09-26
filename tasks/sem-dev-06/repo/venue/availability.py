"""Seat availability."""
from venue.seating import seat_code


def free_seats(rows: int, per_row: int, taken: set[str]) -> list[str]:
    """Codes of the seats not in `taken`, row by row."""
    return [code for r in range(rows) for s in range(per_row) if (code := seat_code(r, s)) not in taken]
