from datetime import date

from binday.reminders import reminder_text
from binday.schedule import next_collection


def test_never_today():
    assert next_collection("north", date(2026, 3, 2)) == date(2026, 3, 9)


def test_south_zone():
    got = next_collection("south", date(2026, 3, 2))
    assert got == date(2026, 3, 5), "some zones get the wrong collection day"


def test_east_next_day():
    assert next_collection("east", date(2026, 3, 2)) == date(2026, 3, 3)


def test_west_from_wednesday():
    assert next_collection("west", date(2026, 3, 4)) == date(2026, 3, 6)


def test_reminder():
    assert reminder_text("east", date(2026, 3, 4)) == "Put your bins out for Tuesday 10 March"
