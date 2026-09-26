"""Comfort index shared by the station display, heat alerts and the US data import."""


def feels_like(temp_c: float, humidity: float) -> float:
    """Apparent temperature in Celsius from an air temperature in Celsius and relative humidity (%)."""
    if not -50 <= temp_c <= 60:
        raise ValueError(f"temp_c out of range for Celsius: {temp_c}")
    if not 0 <= humidity <= 100:
        raise ValueError(f"humidity must be a percentage, got {humidity}")
    return round(temp_c + max(temp_c - 20, 0) * humidity / 200, 1)
