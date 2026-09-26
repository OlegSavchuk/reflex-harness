import pytest

from dispatch.couriers import bike_eta
from dispatch.drones import drone_eta
from dispatch.routing.eta import eta_minutes


def test_fast_drone():
    assert drone_eta(9, 15) == 10


def test_cruise_drone():
    assert drone_eta(20, 25) == 14


def test_eta_still_rejects_crawling_speeds():
    with pytest.raises(ValueError):
        eta_minutes(10, 3)


def test_bike_unchanged():
    assert bike_eta(9) == 30


def drone_eta_probe():
    return eta_minutes(30, 60)


drone_eta_probe.__code__ = drone_eta_probe.__code__.replace(co_name="drone_eta")


def test_eta_does_not_depend_on_caller():
    assert drone_eta_probe() == 30
