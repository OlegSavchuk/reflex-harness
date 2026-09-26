from weather.alerts import heat_alert
from weather.station import display


def test_display():
    assert display(30, 60) == "feels like 33.0 C"


def test_alert():
    assert heat_alert(32, 80) is True
    assert heat_alert(22, 50) is False
