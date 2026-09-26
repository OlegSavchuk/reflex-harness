"""Gain staging shared by playback and the mixer."""


def apply_gain(samples: list[float], gain: float) -> list[float]:
    """Scale samples by a linear gain factor (1.0 = unchanged); clip the result to [-1, 1]."""
    if not 0 < gain <= 8:
        raise ValueError(f"gain must be a linear factor in (0, 8], got {gain}")
    return [max(-1.0, min(1.0, round(s * gain, 4))) for s in samples]
