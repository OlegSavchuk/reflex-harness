"""Run records: cost and tokens include the shared attempt 1 (like cost always did), and the
stored totals hold measured usage only; estimated rows are kept apart, never added."""
import pytest

from fakes import install
from reflex_harness import controller, store
from test_pretty import SCRIPT

SHARED, RUN = "eval-shared-pp-dev-02-T", "eval-fallback-pp-dev-02-T"


def test_run_totals_include_attempt_1_and_only_measured_calls(monkeypatch):
    fake = install(monkeypatch, SCRIPT, tokens=(1000, 200), cost=0.001)
    a1 = controller.shared_first_attempt("pp-dev-02", phase="eval", run_id=SHARED)
    # a Gate 8-style row: the harness's estimate of a server-side query embedding
    store.log_call(run_id=RUN, phase="eval", attempt_n=2, component="embed", model="voyage-4",
                   input_tokens=67, output_tokens=0, cost_usd=4e-6, latency_ms=0, estimated=True)
    doc = controller.run_task("pp-dev-02", "fallback", phase="eval", run_id=RUN, first_attempt=a1,
                              shared_run_id=SHARED, log=lambda m: None)
    measured = [c for c in fake["calls"].docs if c["run_id"] in (RUN, SHARED) and not c.get("estimated")]
    assert [c["run_id"] for c in measured] == [SHARED, RUN, RUN]      # attempt 1 shared, attempts 2-3 own
    stored = fake["runs"].docs[0]
    for rec in (doc, stored):
        assert rec["input_tokens"] == sum(c["input_tokens"] for c in measured) == 3000
        assert rec["output_tokens"] == sum(c["output_tokens"] for c in measured) == 600
        assert rec["cost_usd"] == pytest.approx(sum(c["cost_usd"] for c in measured))
        assert rec["estimated_embed"] == {"calls": 1, "input_tokens": 67, "cost_usd": 4e-6}
    assert stored["shared_attempt"] == {"run_id": SHARED, "cost_usd": a1.cost_usd}


def test_estimated_rows_never_enter_totals(monkeypatch):
    fake = install(monkeypatch, SCRIPT)
    for n in range(3):
        store.log_call(run_id="r", phase="eval", attempt_n=n, component="embed", model="voyage-4",
                       input_tokens=100, output_tokens=0, cost_usd=0.5, latency_ms=0, estimated=True)
    store.log_call(run_id="r", phase="eval", attempt_n=1, component="agent", model="m",
                   input_tokens=10, output_tokens=5, cost_usd=0.01, latency_ms=0)
    t = controller.run_totals(["r"])
    assert (t["input_tokens"], t["output_tokens"], t["cost_usd"]) == (10, 5, 0.01)
    assert t["estimated_embed"] == {"calls": 3, "input_tokens": 300, "cost_usd": 1.5}
    assert len(fake["calls"].docs) == 4


def test_a_shared_attempt_needs_its_run_id():
    with pytest.raises(AssertionError):
        controller.run_task("pp-dev-02", "fallback", phase="eval", first_attempt=object(), shared_run_id=None)
