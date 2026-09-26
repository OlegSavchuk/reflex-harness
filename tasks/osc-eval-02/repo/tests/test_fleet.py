from geo.fleet import nearest_depot, route_length_km


def test_route_length():
    assert route_length_km([(37.7749, -122.4194), (34.0522, -118.2437)]) == 559.1


def test_nearest_depot():
    depots = {"nyc": (40.71, -74.01), "bos": (42.36, -71.06)}
    assert nearest_depot((40.7, -74.0), depots) == "nyc"
