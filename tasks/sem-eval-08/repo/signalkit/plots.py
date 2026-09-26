"""Sparklines."""
from signalkit.pipeline import smooth


def sparkline_points(series: list[float]) -> list[int]:
    return [round(v) for v in smooth(series, 2)]
