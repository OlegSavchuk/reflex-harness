"""Bike couriers ride at a fixed 18 km/h."""
from dispatch.routing.eta import eta_minutes


def bike_eta(distance_km: float) -> int:
    return eta_minutes(distance_km, 18)
