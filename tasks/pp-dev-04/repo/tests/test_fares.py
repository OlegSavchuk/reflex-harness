from transit.cards import charge
from transit.fares import fare
from transit.planner import cheapest
from transit.receipts import receipt_line


def test_sixteen_pays_full_fare():
    assert fare("Central", "Museum", 16) == 250


def test_airport_trip():
    got = fare("Harbour", "Airport", 40)
    assert got == 300, "fares are wrong for some journeys"


def test_adult_two_zones():
    assert fare("Central", "Hillside", 30) == 300


def test_child_fare():
    assert fare("Museum", "Hillside", 10) == 125


def test_charge():
    assert charge(1000, "Central", "Stadium", 40) == 750


def test_cheapest():
    assert cheapest([("Central", "Hillside"), ("Harbour", "Museum")], 30) == ("Harbour", "Museum")


def test_receipt():
    assert receipt_line("Stadium", "Central", 12) == "Stadium -> Central: 1.25"
