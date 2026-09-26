"""Box-office reports."""
from datetime import time

from cinema.tickets import ticket_price


def revenue(sales: list[tuple[time, bool, int]]) -> int:
    """Revenue in cents for (start time, student, tickets sold) rows."""
    return sum(ticket_price(starts, student) * n for starts, student, n in sales)
