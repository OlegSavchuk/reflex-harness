"""GeoJSON import. GeoJSON coordinates are [longitude, latitude]."""
from geo.distance import haversine_km


def linestring_length_km(feature: dict) -> float:
    pts = [tuple(c) for c in feature["geometry"]["coordinates"]]
    return round(sum(haversine_km(a, b) for a, b in zip(pts, pts[1:])), 1)


def feature_count(collection: dict) -> int:
    return len(collection.get("features", []))
