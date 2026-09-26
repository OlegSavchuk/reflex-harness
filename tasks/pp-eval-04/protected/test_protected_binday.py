from datetime import date

from binday.schedule import next_collection
from binday.zones import collection_weekday


def test_south_is_thursday():
    assert collection_weekday("south") == 3


def test_south_on_its_own_day():
    assert next_collection("south", date(2026, 3, 5)) == date(2026, 3, 12)


def test_west_on_friday():
    assert next_collection("west", date(2026, 3, 6)) == date(2026, 3, 13)


def _day(zone):
    return collection_weekday(zone)


def test_weekday_outside_a_test_function():
    assert _day("south") == 3
