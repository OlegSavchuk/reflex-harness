"""Signal smoothing."""
from signalkit.filters.rolling import moving_average


def smooth(series: list[float], window: int = 3) -> list[float]:
    """Smoothed series; a series shorter than the window is returned unchanged."""
    if len(series) < window:
        return list(series)
    return moving_average(series, window)
