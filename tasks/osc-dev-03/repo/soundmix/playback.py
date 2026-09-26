"""Playback. Volume comes from the player's settings as a linear factor."""
from soundmix.dsp.gain import apply_gain


def render(samples: list[float], volume: float = 1.0) -> list[float]:
    return apply_gain(samples, volume)


def fade_out(samples: list[float]) -> list[float]:
    n = len(samples)
    return [apply_gain([s], (n - i) / n)[0] for i, s in enumerate(samples)]
