"""Latency reports."""
from perfwatch.stats.summary import summarize


def latency_report(samples_ms: list[float]) -> str:
    """One-line report of p50, p90 and max latency in milliseconds."""
    if not samples_ms:
        return "no samples"
    s = summarize(samples_ms)
    return f"p50={s['p50']:g}ms p90={s['p90']:g}ms max={s['max']:g}ms"
