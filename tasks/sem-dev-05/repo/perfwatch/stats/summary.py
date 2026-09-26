"""Summary statistics."""


def _nearest_rank(sorted_values: list[float], pct: float) -> float:
    """Nearest-rank percentile of an ascending list (pct in (0, 100])."""
    idx = int(pct / 100 * len(sorted_values))
    return sorted_values[min(idx, len(sorted_values) - 1)]


def summarize(values: list[float]) -> dict[str, float]:
    s = sorted(values)
    return {"p50": _nearest_rank(s, 50), "p90": _nearest_rank(s, 90), "max": s[-1]}
