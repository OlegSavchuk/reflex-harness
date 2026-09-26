from reflex_harness.context import seed_function_keys
from reflex_harness.controller import same_strategy
from reflex_harness.runner import LocalRunner, load_task

FOCAL = "gradebook/stats.py::class_average"
SEED = {"gradebook/stats.py::class_average", "gradebook/stats.py::pass_rate",
        "gradebook/report.py::course_line", "gradebook/models.py::__init__",
        "gradebook/models.py::add", "gradebook/models.py::count"}
FAILING = ["tests/test_stats.py::test_average_second_course"]


def test_seed_function_keys_match_the_seed():
    runner = LocalRunner()
    ws = runner.prepare(load_task("sem-dev-01"))
    try:
        assert seed_function_keys(ws) == SEED
    finally:
        runner.cleanup(ws)


def test_hack_moved_into_a_new_helper_is_same_strategy():
    # sem-dev-01 pattern: attempt 1 edits the focal and creates a helper; attempt 2 edits only the helper
    prev = ["gradebook/stats.py::<module>", "gradebook/stats.py::_valid_scores", FOCAL]
    cur = ["gradebook/stats.py::_valid_scores"]
    assert same_strategy(prev, cur, FOCAL, FAILING, SEED)
    assert same_strategy(cur, ["gradebook/stats.py::<module>", "gradebook/stats.py::_valid_scores"],
                         FOCAL, FAILING, SEED)


def test_not_same_strategy_when_failures_clear():
    assert not same_strategy([FOCAL], [FOCAL], FOCAL, [], SEED)


def test_edit_outside_the_region_is_not_same_strategy():
    # the real fix lives in another file's seed function
    assert not same_strategy([FOCAL], ["gradebook/models.py::__init__"], FOCAL, FAILING, SEED)
    # module-level edit in another file (e.g. a lookup table) is outside the region
    assert not same_strategy([FOCAL], ["gradebook/models.py::<module>"], FOCAL, FAILING, SEED)


def test_sibling_seed_function_is_outside_the_region():
    # the actual sem-dev-01 smoke run: attempt 1 also rewrote pass_rate (a seed sibling)
    prev = ["gradebook/stats.py::<module>", "gradebook/stats.py::_scores", FOCAL,
            "gradebook/stats.py::pass_rate"]
    assert not same_strategy(prev, ["gradebook/stats.py::_scores"], FOCAL, FAILING, SEED)


def test_replay_reuses_the_shared_patch_without_a_model_call(monkeypatch):
    from reflex_harness import agent
    from reflex_harness.config import CONFIGS_R1
    from reflex_harness.context import pin_focal
    from reflex_harness.controller import AttemptResult, run_attempt

    def no_call(*a, **k):
        raise AssertionError("replay must not call the model")
    monkeypatch.setattr(agent, "call", no_call)
    task = load_task("osc-dev-01")
    runner = LocalRunner()
    ws = runner.prepare(task)
    try:
        base = runner.run(ws, task.diag_cmd, 60)
        tax = (ws.path / "billing/tax.py").read_text().replace(
            "round(amount_cents * (1 + rate))", "round(amount_cents * (1 + rate), 2)")
        shared = AttemptResult("focused", "traceback", {}, {}, base, [], {"files": [
            {"path": "billing/tax.py", "content": tax}]}, "round to cents", 0.0012, [], False, False,
            prompt="SHARED PROMPT")
        cfg = next(c for c in CONFIGS_R1 if c["config_id"] == "focused")
        a = run_attempt(runner, ws, base, cfg, pin_focal(ws, base), [], run_id="t", phase="dev",
                        attempt_n=1, verify=False, replay=shared)
        assert a.prompt == "SHARED PROMPT" and a.cost_usd == 0.0012 and a.note == "round to cents"
        assert a.edited == ["billing/tax.py::apply_tax"] and a.regressed   # invoice tests break
    finally:
        runner.cleanup(ws)
