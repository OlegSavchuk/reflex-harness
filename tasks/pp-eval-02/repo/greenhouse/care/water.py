"""Watering rules."""

# Base daily water in ml per plant.
BASE_ML = {"tomato": 800, "basil": 150, "fern": 300, "cactus": 40}


def _heat_factor(temp_c: float) -> float:
    """1.0 below 25 C, 1.5 from 25 C up to 32 C, 2.0 at 32 C and above."""
    if temp_c >= 32:
        return 2.0
    if temp_c >= 28:
        return 1.5
    return 1.0


def daily_water_ml(plant: str, temp_c: float) -> int:
    return round(BASE_ML[plant] * _heat_factor(temp_c))
