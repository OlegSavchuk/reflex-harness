"""Travel-time estimates shared by trucks, couriers and drones."""
import math


def eta_minutes(distance_km: float, speed_kmh: float) -> int:
    """Whole minutes (rounded up) to cover distance_km at speed_kmh."""
    if not 5 <= speed_kmh <= 250:
        raise ValueError(f"speed_kmh out of range: {speed_kmh}")
    if distance_km < 0:
        raise ValueError("distance_km must be non-negative")
    return math.ceil(round(distance_km / speed_kmh * 60, 6))
