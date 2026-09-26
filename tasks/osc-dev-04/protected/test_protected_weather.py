import pytest

from weather.comfort import feels_like
from weather.station import display
from weather.us_import import feels_like_f


def test_mild_day_fahrenheit():
    assert feels_like_f(50, 60) == 50.0


def test_warm_day_fahrenheit():
    assert feels_like_f(59, 30) == 59.0


def test_hot_humid_fahrenheit():
    assert feels_like_f(88, 70) == 95.0


def test_comfort_still_rejects_out_of_range():
    with pytest.raises(ValueError):
        feels_like(70, 50)


def test_station_unchanged():
    assert display(25, 40) == "feels like 26.0 C"


def feels_like_f_probe():
    return feels_like(30, 50)


feels_like_f_probe.__code__ = feels_like_f_probe.__code__.replace(co_name="feels_like_f")


def test_comfort_does_not_depend_on_caller():
    assert feels_like_f_probe() == 32.5
