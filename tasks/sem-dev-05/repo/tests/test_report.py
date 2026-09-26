from perfwatch.dashboard import panel
from perfwatch.report import latency_report


def test_ten_samples():
    assert latency_report(list(range(1, 11))) == "p50=5ms p90=9ms max=10ms"


def test_panel():
    assert panel("api", [40, 10, 30, 20]) == "api: p50=20ms p90=40ms max=40ms"


def test_no_samples():
    assert latency_report([]) == "no samples"
