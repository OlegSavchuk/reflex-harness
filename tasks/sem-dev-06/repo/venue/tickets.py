"""Tickets."""
from venue.seating import seat_code


def ticket_line(event: str, row: int, seat: int) -> str:
    return f"{event} | seat {seat_code(row, seat)}"
