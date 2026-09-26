"""Training reports."""
from fitlog.core.pace import pace


def best_pace(runs: list[tuple[int, int]]) -> str:
    """Fastest pace among (distance_m, duration_s) runs."""
    if not runs:
        return "no runs"
    distance_m, duration_s = min(runs, key=lambda r: r[1] / r[0])
    return pace(distance_m, duration_s)
