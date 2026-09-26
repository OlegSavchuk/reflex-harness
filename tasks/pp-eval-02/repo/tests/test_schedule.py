from greenhouse.rota import rota_line
from greenhouse.schedule import watering_plan


def test_rounds_up_to_whole_litres():
    assert watering_plan({"basil": 2, "fern": 1}, 20, 2) == 2


def test_warm_day():
    got = watering_plan({"tomato": 1}, 26, 1)
    assert got == 2, "plans are wrong for some conditions"


def test_cool_week():
    assert watering_plan({"tomato": 2}, 18, 5) == 8


def test_hot_day():
    assert watering_plan({"tomato": 1, "cactus": 5}, 33, 1) == 2


def test_rota():
    assert rota_line("Mon", {"basil": 4}, 22) == "Mon: 1 L"
