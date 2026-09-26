"""Fare zones. Zone 1: Central, Harbour. Zone 2: Museum, Stadium. Zone 3: Hillside, Airport."""

ZONES = {"Central": 1, "Harbour": 1, "Museum": 2, "Stadium": 2, "Hillside": 3, "Airport": 4}


def zone_of(station: str) -> int:
    return ZONES[station]
