from geo.geojson_import import feature_count, linestring_length_km


def line(*coords):
    return {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [list(c) for c in coords]}}


def test_linestring_west_coast():
    assert linestring_length_km(line((-122.4194, 37.7749), (-118.2437, 34.0522))) == 559.1


def test_linestring_europe():
    assert linestring_length_km(line((2.3522, 48.8566), (-0.1276, 51.5072))) == 343.5


def test_linestring_single_point():
    assert linestring_length_km(line((2.3522, 48.8566))) == 0


def test_feature_count():
    assert feature_count({"features": [{}, {}]}) == 2
