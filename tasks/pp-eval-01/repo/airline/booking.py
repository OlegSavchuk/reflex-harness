"""Booking extras."""
from airline.fees import baggage_fee


def trip_extras(cabin: str, bags_out: list[float], bags_back: list[float]) -> int:
    """Baggage fees for both legs of a return trip, in cents."""
    return baggage_fee(cabin, bags_out) + baggage_fee(cabin, bags_back)
