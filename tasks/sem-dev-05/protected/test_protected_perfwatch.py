from perfwatch.report import latency_report
from perfwatch.stats.summary import summarize


def test_summary_twenty_values():
    assert summarize(list(range(1, 21))) == {"p50": 10, "p90": 18, "max": 20}


def test_summary_single_value():
    assert summarize([7]) == {"p50": 7, "p90": 7, "max": 7}


def test_report_five_samples():
    assert latency_report([100, 200, 300, 400, 500]) == "p50=300ms p90=500ms max=500ms"


def _summ(values):
    return summarize(values)


def test_summary_outside_a_test_function():
    assert _summ(list(range(1, 11)))["p50"] == 5
