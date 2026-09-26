"""Truck routes. Speeds are km/h."""
from dispatch.routing.eta import eta_minutes


def truck_eta(distance_km: float, speed_kmh: float = 80) -> int:
    return eta_minutes(distance_km, speed_kmh)
