"""Mixer channel strip. Fader positions are in decibels (0 dB leaves the signal unchanged)."""
from soundmix.dsp.gain import apply_gain


def channel_output(samples: list[float], fader_db: float) -> list[float]:
    return apply_gain(samples, fader_db)


def peak(samples: list[float]) -> float:
    return max((abs(s) for s in samples), default=0.0)
