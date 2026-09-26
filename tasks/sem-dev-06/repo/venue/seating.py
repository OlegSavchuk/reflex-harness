"""Seat codes."""
from venue.labels import row_label


def seat_code(row: int, seat: int) -> str:
    """Printed code for a 0-based row and seat: the row label, then the 1-based seat number (B7)."""
    if row < 0 or seat < 0:
        raise ValueError("row and seat must be non-negative")
    return f"{row_label(row)}{seat + 1}"
