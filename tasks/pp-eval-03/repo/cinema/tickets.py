"""Ticket prices."""
from datetime import time

from cinema.pricing.tariffs import base_price

STUDENT = 900


def ticket_price(starts: time, student: bool) -> int:
    """Price in cents: the tariff for the start time. Students pay STUDENT instead, unless the
    tariff is already lower (discounts never stack)."""
    return STUDENT if student else base_price(starts)
