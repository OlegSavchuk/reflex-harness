"""Great-circle distance shared by fleet routing and map imports."""
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distance between two (latitude, longitude) points in km."""
    for lat, lon in (a, b):
        if not -90 <= lat <= 90:
            raise ValueError(f"latitude out of range: {lat}")
        if not -180 <= lon <= 180:
            raise ValueError(f"longitude out of range: {lon}")
    lat1, lon1, lat2, lon2 = map(radians, (*a, *b))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(h))
