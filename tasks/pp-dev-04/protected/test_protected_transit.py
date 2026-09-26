from transit.fares import fare
from transit.network.zones import zone_of


def test_airport_is_zone_three():
    assert zone_of("Airport") == 3
    assert zone_of("Hillside") == 3


def test_child_to_airport():
    assert fare("Museum", "Airport", 12) == 125


def test_age_boundary():
    assert fare("Harbour", "Stadium", 15) == 125
    assert fare("Harbour", "Stadium", 16) == 250


def _zone(station):
    return zone_of(station)


def test_zone_outside_a_test_function():
    assert _zone("Airport") == 3
