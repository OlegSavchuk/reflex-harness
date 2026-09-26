"""Price labels in the app."""
from datetime import time

from cinema.tickets import ticket_price


def price_label(starts: time, student: bool) -> str:
    return f"{ticket_price(starts, student) / 100:.2f}"
