"""Station display (Celsius)."""
from weather.comfort import feels_like


def display(temp_c: float, humidity: float) -> str:
    return f"feels like {feels_like(temp_c, humidity):.1f} C"
