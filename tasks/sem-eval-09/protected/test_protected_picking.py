from picking.model.location import Location
from picking.route import pick_route
from picking.waves import first_picks


def test_walk_key_is_numeric():
    assert Location("12-3").walk_key() == (12, 3)
    assert Location("9-10").walk_key() < Location("10-2").walk_key()


def test_route_across_many_aisles():
    lines = [("a", Location("11-1")), ("b", Location("2-4")), ("c", Location("1-30")),
             ("d", Location("20-1")), ("e", Location("2-10"))]
    assert pick_route(lines) == ["c", "b", "e", "a", "d"]


def test_first_picks_two_digit_aisles():
    assert first_picks({"o": [("S", Location("10-1")), ("T", Location("8-1"))]}) == {"o": "T"}


def _key(loc):
    return loc.walk_key()


def test_key_outside_a_test_function():
    assert _key(Location("2-10")) == (2, 10)
