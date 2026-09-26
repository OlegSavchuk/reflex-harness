"""Fares."""
from transit.network.zones import zone_of

CHILD_AGE = 16


def fare(origin: str, dest: str, age: int) -> int:
    """Fare in cents: 200 plus 50 for each zone boundary crossed. Riders under CHILD_AGE pay half,
    rounded down to the cent."""
    cents = 200 + 50 * abs(zone_of(origin) - zone_of(dest))
    return cents // 2 if age <= CHILD_AGE else cents
