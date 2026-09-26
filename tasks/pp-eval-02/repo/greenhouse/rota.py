"""Daily rota."""
from greenhouse.schedule import watering_plan


def rota_line(day: str, plants: dict[str, int], temp_c: float) -> str:
    return f"{day}: {watering_plan(plants, temp_c, 1)} L"
