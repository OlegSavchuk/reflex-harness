from dispatch.couriers import bike_eta
from dispatch.trucks import truck_eta


def test_truck():
    assert truck_eta(120) == 90


def test_bike():
    assert bike_eta(4.5) == 15
