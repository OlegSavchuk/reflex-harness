"""Smart cards."""
from transit.fares import fare


def charge(balance_cents: int, origin: str, dest: str, age: int) -> int:
    """Balance after paying the fare; a card cannot go negative (ValueError)."""
    left = balance_cents - fare(origin, dest, age)
    if left < 0:
        raise ValueError("insufficient balance")
    return left
