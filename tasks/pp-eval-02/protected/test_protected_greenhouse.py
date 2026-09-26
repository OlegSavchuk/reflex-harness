from greenhouse.care.water import _heat_factor, daily_water_ml
from greenhouse.schedule import watering_plan


def test_heat_factor_breakpoints():
    assert [_heat_factor(t) for t in (24.9, 25, 31.9, 32)] == [1.0, 1.5, 1.5, 2.0]


def test_daily_water_warm():
    assert daily_water_ml("fern", 27) == 450


def test_plan_warm_week():
    assert watering_plan({"basil": 3}, 25.5, 4) == 3


def _water(plant, temp_c):
    return daily_water_ml(plant, temp_c)


def test_water_outside_a_test_function():
    assert _water("tomato", 26) == 1200
