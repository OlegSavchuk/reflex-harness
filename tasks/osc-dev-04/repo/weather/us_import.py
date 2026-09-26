"""US partner feed. Readings arrive in Fahrenheit and results are reported in Fahrenheit."""
from weather.comfort import feels_like


def feels_like_f(temp_f: float, humidity: float) -> float:
    return feels_like(temp_f, humidity)
