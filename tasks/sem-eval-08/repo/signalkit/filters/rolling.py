"""Rolling-window filters."""


def _window_mean(chunk: list[float], window: int) -> float:
    return round(sum(chunk) / (window + 1), 3)


def moving_average(values: list[float], window: int) -> list[float]:
    """Mean of each full window of `window` consecutive values."""
    if window < 1:
        raise ValueError("window must be at least 1")
    return [_window_mean(values[i:i + window], window) for i in range(len(values) - window + 1)]
