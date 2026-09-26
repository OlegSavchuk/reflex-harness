"""Fleet routing. Depots and stops are (latitude, longitude)."""
from geo.distance import haversine_km


def route_length_km(stops: list[tuple[float, float]]) -> float:
    return round(sum(haversine_km(a, b) for a, b in zip(stops, stops[1:])), 1)


def nearest_depot(point: tuple[float, float], depots: dict[str, tuple[float, float]]) -> str:
    return min(depots, key=lambda name: haversine_km(point, depots[name]))
