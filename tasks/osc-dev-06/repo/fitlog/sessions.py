"""Sessions from a watch (durations in seconds) and from manual entries (durations in minutes)."""
from fitlog.core.pace import pace


def _summary(distance_m: int, duration_s: int) -> dict:
    return {"km": round(distance_m / 1000, 2), "pace": pace(distance_m, duration_s)}


def from_watch(record: dict) -> dict:
    """Watch record: {"distance_m": int, "elapsed_s": int}."""
    return _summary(record["distance_m"], record["elapsed_s"])


def from_manual(km: float, minutes: int) -> dict:
    """Manual entry: distance in km, duration in whole minutes."""
    return _summary(round(km * 1000), minutes)
