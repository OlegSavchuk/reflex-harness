"""Watering schedules."""
import math

from greenhouse.care.water import daily_water_ml


def watering_plan(plants: dict[str, int], temp_c: float, days: int) -> int:
    """Litres to set aside for `days` days: each plant type's daily water times its count,
    summed over types and days, in whole litres rounded up."""
    total_ml = sum(daily_water_ml(p, temp_c) * n for p, n in plants.items()) * days
    return round(total_ml / 1000)
