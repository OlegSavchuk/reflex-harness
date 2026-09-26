"""Ticket tariffs in cents. Screenings starting before 15:00 are matinees."""
from datetime import time

ADULT = 1200
MATINEE = 800
MATINEE_END = time(16, 0)


def base_price(starts: time) -> int:
    """The matinee tariff for a screening that starts before 15:00, the adult tariff otherwise."""
    return MATINEE if starts < MATINEE_END else ADULT
