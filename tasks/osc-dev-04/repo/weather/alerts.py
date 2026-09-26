"""Heat alerts (Celsius)."""
from weather.comfort import feels_like

THRESHOLD_C = 35.0


def heat_alert(temp_c: float, humidity: float) -> bool:
    return feels_like(temp_c, humidity) >= THRESHOLD_C
