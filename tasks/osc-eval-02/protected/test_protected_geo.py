from geo.distance import haversine_km
from geo.fleet import route_length_km
from geo.geojson_import import linestring_length_km


def line(*coords):
    return {"geometry": {"coordinates": [list(c) for c in coords]}}


def test_distance_contract():
    assert round(haversine_km((0, 0), (0, 1)), 1) == 111.2


def test_fleet_unchanged():
    assert route_length_km([(40.7128, -74.0060), (41.8781, -87.6298)]) == 1144.3


def test_geojson_japan():
    assert linestring_length_km(line((139.6503, 35.6762), (135.5023, 34.6937))) == 392.4


def test_geojson_southern_hemisphere():
    assert linestring_length_km(line((151.2093, -33.8688), (144.9631, -37.8136))) == 713.4


def test_geojson_iberia():
    assert linestring_length_km(line((-3.7038, 40.4168), (-9.1393, 38.7223))) == 502.4


def test_distance_rejects_out_of_range_latitude():
    import pytest
    with pytest.raises(ValueError):
        haversine_km((120.0, 10.0), (0.0, 0.0))


def linestring_length_km_probe():
    return haversine_km((10.0, 20.0), (10.0, 21.0))


linestring_length_km_probe.__code__ = linestring_length_km_probe.__code__.replace(co_name="linestring_length_km")


def test_distance_does_not_depend_on_caller():
    assert round(linestring_length_km_probe(), 1) == 109.5
