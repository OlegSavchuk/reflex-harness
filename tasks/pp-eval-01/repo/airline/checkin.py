"""Check-in desk."""
from airline.fees import baggage_fee


def checkin_summary(name: str, cabin: str, bags: list[float]) -> str:
    n = len(bags)
    return f"{name} ({cabin}): {n} bag{'s' if n != 1 else ''}, fee {baggage_fee(cabin, bags) / 100:.2f}"
