"""--pretty is presentation only: the stored run is identical with and without it."""
import copy

import pytest

from reflex_harness import agent, cli, config, controller, store
from reflex_harness.pretty import Pretty, pytest_summary
from reflex_harness.runner import load_task

TASK = load_task("pp-dev-02")
PAY = (TASK.repo / "payroll/pay.py").read_text()
TAX = (TASK.repo / "payroll/tax.py").read_text()
FIX1 = PAY.replace("max(hours - 40, 0) * rate_cents)", "max(hours - 40, 0) * rate_cents * 1.5)")
TWEAK = FIX1.replace("    return gross - income_tax(gross)", "    net = gross - income_tax(gross)\n    return net")
FIX2 = TAX.replace("(None, 0.45)", "(None, 0.35)")
# attempt 1 fixes bug #1, attempt 2 re-edits the focal (same strategy), attempt 3 fixes both
SCRIPT = [{"payroll/pay.py": FIX1}, {"payroll/pay.py": TWEAK}, {"payroll/pay.py": FIX1, "payroll/tax.py": FIX2}]


class FakeCollection:
    def __init__(self, docs=()):
        self.docs = [copy.deepcopy(d) for d in docs]

    @staticmethod
    def _match(d, flt):
        return all(d.get(k) == v for k, v in (flt or {}).items())

    def insert_one(self, doc):
        self.docs.append(copy.deepcopy(doc))

    def find(self, flt=None, projection=None):
        return [copy.deepcopy(d) for d in self.docs if self._match(d, flt)]

    def find_one(self, flt=None, projection=None):
        return next(iter(self.find(flt)), None)

    def distinct(self, key, flt=None):
        return list(dict.fromkeys(d[key] for d in self.docs if self._match(d, flt)))

    def aggregate(self, pipeline):  # only the run-total pipeline in run_task
        rows = [d for d in self.docs if self._match(d, pipeline[0]["$match"])]
        if not rows:
            return iter([])
        return iter([{"c": sum(r["cost_usd"] for r in rows), "i": sum(r["input_tokens"] for r in rows),
                      "o": sum(r["output_tokens"] for r in rows)}])


class FakeDB(dict):
    def __missing__(self, name):
        self[name] = FakeCollection()
        return self[name]


def run_cli(monkeypatch, argv):
    fake = FakeDB(configs=FakeCollection([{**c, "registry": config.REGISTRY} for c in config.CONFIGS_R1]))
    monkeypatch.setattr(controller, "db", lambda: fake)
    monkeypatch.setattr(store, "db", lambda: fake)

    def scripted(messages, *, run_id, phase, attempt_n, step="patch", **_):
        store.log_call(run_id=run_id, phase=phase, attempt_n=attempt_n, component="agent", model="fake",
                       input_tokens=1000, output_tokens=200, cost_usd=0.001, latency_ms=0)
        files = SCRIPT[attempt_n - 1]
        return agent.AgentReply(data={"files": [{"path": p, "content": c} for p, c in files.items()], "note": "x"},
                                model="fake", model_reported=None, input_tokens=1000, output_tokens=200,
                                cost_usd=0.001, latency_ms=0, error=None)
    monkeypatch.setattr(agent, "call", scripted)
    cli.main(argv)
    return fake


def normalised(fake):
    """Everything the run stored, minus wall-clock fields and the timestamped run id."""
    out = {}
    for name in ("attempts", "decisions", "runs", "calls"):
        rows = []
        for d in fake[name].docs:
            d = {k: v for k, v in d.items() if k not in ("created_at", "latency_ms")}
            rows.append(repr(d).replace(fake["runs"].docs[0]["run_id"], "<run>"))
        out[name] = rows
    return out


@pytest.mark.parametrize("arm", ["fallback", "plain_retry"])
def test_pretty_changes_output_only_never_the_stored_run(monkeypatch, capsys, arm):
    base = ["run", "--task", "pp-dev-02", "--arm", arm, "--phase", "demo"]
    plain = normalised(run_cli(monkeypatch, base))
    plain_out = capsys.readouterr().out
    pretty = normalised(run_cli(monkeypatch, base + ["--pretty"]))
    pretty_out = capsys.readouterr().out
    assert plain == pretty                                   # attempts, prompts, decisions, runs, calls
    assert len(plain["attempts"]) == 3 and "'verified_fix': True" in plain["runs"][0]
    assert "attempt 1 [focused]" in plain_out and "attempt 1 [focused]" not in pretty_out   # no raw logs
    assert "[ REFLEX ] task pp-dev-02 · arm " + arm in pretty_out
    assert "[ ATTEMPT 1 ] (focused) · editing net_pay → VISIBLE TESTS 5/6" in pretty_out
    assert "[ FINAL ] VISIBLE TESTS ✓ · HIDDEN TESTS ✓ (4 passed in " in pretty_out
    assert "STATIC CHECK ✓" in pretty_out and "FIXED  ·  $0.0030  ·  3,600 tokens" in pretty_out
    if arm == "fallback":
        for line in ("[ SAME STRATEGY ] detected", "[ RESET ] → seed hash verified", "[ SWITCH ] → caller",
                     "[ ATTEMPT 3 ] (caller) · editing net_pay, module-level code → VISIBLE TESTS 6/6"):
            assert line in pretty_out
    else:
        assert "SWITCH" not in pretty_out and "SAME STRATEGY" not in pretty_out


def test_memory_line_and_summary_formatting():
    p = Pretty(model="m", color=False, stream=open("/dev/null", "w"), checkpoint_outcomes=lambda cid: ["dependency"])
    p("selection", arm="memory", row={"status": "selected", "retrieved": [
        {"checkpoint_id": "mem-v1-sem-dev-02", "family": "semantic_repetition", "semantic_score": 0.8312}]})
    p("final", stop_reason="verification_failed", verified_fix=False, visible_pass=True,
      verify={"summary": {"passed": 3, "failed": 1}, "duration_s": 0.4, "failed": ["t"], "static_failed": True,
              "timed_out": False}, cost_usd=0.01, input_tokens=10, output_tokens=5)
    assert p.lines[0] == ("[ MONGODB MEMORY ] → nearest past case: mem-v1-sem-dev-02 (semantic_repetition, "
                          "similarity 0.83) → solved by dependency")
    assert p.lines[1] == "[ FINAL ] VISIBLE TESTS ✓ · HIDDEN TESTS ✗ (1 failed, 3 passed in 0.40s) · STATIC CHECK ✗"
    assert "NOT FIXED" in p.lines[2] and "visible tests passed, hidden tests failed" in p.lines[2]
    assert pytest_summary({"summary": {"error": 2}, "duration_s": 1}) == "2 errors in 1.00s"


def test_regression_attempt_line_counts_the_broken_tests():
    p = Pretty(model="m", color=False, stream=open("/dev/null", "w"))
    base = dict(config_id="focused", edited=["q.py::quote"], visible_passed=2, visible_total=5, error=None,
                solved=False, rolled_back=True)
    p("attempt", attempt_n=1, regressed=["t::a"], trigger="regression", **base)
    p("attempt", attempt_n=2, regressed=["t::a", "t::b"], trigger="regression", **base)
    p("attempt", attempt_n=3, regressed=["t::a"], trigger=None, **base)   # plain_retry: nothing triggered
    assert p.lines[0].endswith("VISIBLE TESTS 2/5 · 1 previously passing test broke")
    assert p.lines[1].endswith("VISIBLE TESTS 2/5 · 2 previously passing tests broke")
    assert p.lines[2].endswith("VISIBLE TESTS 2/5")
