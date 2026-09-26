"""Dashboard panels."""
from perfwatch.report import latency_report


def panel(service: str, samples_ms: list[float]) -> str:
    return f"{service}: {latency_report(samples_ms)}"
