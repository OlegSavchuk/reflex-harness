"""Checkout."""
from venue.seating import seat_code


def confirm(order_id: str, seats: list[tuple[int, int]]) -> str:
    codes = ", ".join(seat_code(r, s) for r, s in seats)
    return f"Order {order_id}: {codes}"
