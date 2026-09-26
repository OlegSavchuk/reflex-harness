"""Baskets."""
from datetime import time

from cinema.tickets import ticket_price


def basket_total(seats: list[tuple[time, bool]]) -> int:
    """Total in cents for (start time, student) seats."""
    return sum(ticket_price(starts, student) for starts, student in seats)
