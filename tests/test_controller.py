import pytest

from reflex_harness.context import focal_region, pin_focal, seed_function_keys
from reflex_harness.controller import progress_moved, same_strategy
from reflex_harness.runner import LocalRunner, load_task

FOCAL = "gradebook/stats.py::class_average"
SEED = {"gradebook/stats.py::class_average", "gradebook/stats.py::pass_rate",
        "gradebook/report.py::course_line", "gradebook/models.py::__init__",
        "gradebook/models.py::add", "gradebook/models.py::count"}
FAILING = ["tests/test_stats.py::test_average_second_course"]


@pytest.fixture(scope="module")
def region():
    runner = LocalRunner()
    ws = runner.prepare(load_task("sem-dev-01"))
    try:
        base = runner.run(ws, ws.task.diag_cmd, 60)
        assert seed_function_keys(ws) == SEED
        yield focal_region(ws, pin_focal(ws, base), base)
    finally:
        runner.cleanup(ws)


def test_region_is_focal_plus_seed_functions_the_failing_tests_call(region):
    # failing tests: test_average_second_course (GradeBook, add, class_average), test_pass_rate (.., pass_rate)
    assert region.fixed == {FOCAL, "gradebook/stats.py::pass_rate", "gradebook/models.py::add"}
    assert not region.inside("gradebook/models.py::__init__")      # where the real fix is
    assert region.inside("gradebook/stats.py::_brand_new_helper")   # agent-created


def test_sem_dev_01_pattern_sibling_edit_is_same_strategy(region):
    # shared attempt 1 rewrote class_average AND its seed sibling pass_rate and created a helper;
    # attempt 2 moved the hack into more new helpers
    prev = ["gradebook/stats.py::<module>", "gradebook/stats.py::_scores_for_course", FOCAL,
            "gradebook/stats.py::pass_rate"]
    cur = ["gradebook/stats.py::<module>", "gradebook/stats.py::_course_key",
           "gradebook/stats.py::_scores_for_course"]
    assert same_strategy(prev, cur, region, FAILING)


def test_not_same_strategy_when_failures_clear(region):
    assert not same_strategy([FOCAL], [FOCAL], region, [])


def test_edit_outside_the_region_is_not_same_strategy(region):
    assert not same_strategy([FOCAL], ["gradebook/models.py::__init__"], region, FAILING)
    assert not same_strategy([FOCAL], ["gradebook/models.py::<module>"], region, FAILING)


def test_step7_shrinking_hack_moved_into_a_new_helper_is_not_progress_that_moved(region):
    before = FAILING + ["tests/test_stats.py::test_pass_rate"]
    assert not progress_moved(["gradebook/stats.py::_fresh_helper"], before, FAILING, region)
    assert not progress_moved([FOCAL, "gradebook/stats.py::pass_rate"], before, FAILING, region)


def test_step7_shrinkage_outside_the_region_counts_as_moved(region):
    before = FAILING + ["tests/test_stats.py::test_pass_rate"]
    assert progress_moved(["gradebook/models.py::__init__"], before, FAILING, region)
    assert not progress_moved(["gradebook/models.py::__init__"], FAILING, FAILING, region)  # no shrink


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


def test_selection_log_classifies_runs_where_selection_never_acted():
    from reflex_harness.controller import selection_log
    row = {"chosen_config_id": "dependency", "retrieved": [
        {"checkpoint_id": "a", "family": "semantic_repetition", "fusion_score": 0.03},
        {"checkpoint_id": "b", "family": "oscillation", "fusion_score": 0.02}]}
    sw = selection_log("memory", "semantic_repetition", "solved", 2, [{"attempt_n": 2, "trigger": "same_strategy"}], row, 3)
    assert sw["pre_selection_end"] is None and sw["chosen_matches_designed"] is True
    assert [n["family"] for n in sw["neighbours"]] == ["semantic_repetition", "oscillation"]
    assert selection_log("fallback", "oscillation", "verification_failed", None, [], None, 2)["pre_selection_end"] \
        == "diagnostics_passed_before_switch (verification_failed)"
    assert selection_log("memory", "oscillation", "budget_exhausted", None,
                         [{"attempt_n": 3, "trigger": "same_strategy"}], None, 3)["pre_selection_end"] == "trigger_at_final_attempt"
    assert selection_log("memory", "oscillation", "budget_exhausted", None, [], None, 3)["pre_selection_end"] == "no_trigger"
    assert selection_log("plain_retry", "oscillation", "budget_exhausted", None, [], None, 3)["pre_selection_end"] == "arm_has_no_selection"


class _Attempts:
    def distinct(self, *a, **k):
        return ["focused"]


def _random_row(monkeypatch, repeat, task_id="sem-eval-01"):
    from reflex_harness import agent, controller, narrator
    from reflex_harness.config import CONFIGS_R1

    def forbidden(*a, **k):
        raise AssertionError("the random arm must not retrieve, narrate or call a model")
    monkeypatch.setattr(narrator, "narrate_task", forbidden)
    monkeypatch.setattr(agent, "call", forbidden)
    monkeypatch.setattr(controller, "db", lambda: {"attempts": _Attempts()})  # no checkpoints access
    return controller.select_next("random", task=load_task(task_id), run_id="r", phase="dev", attempt_n=1,
                                  trigger="regression", configs={c["config_id"]: c for c in CONFIGS_R1},
                                  snapshot="mem-v1", registry="r1", protocol="p1", repeat=repeat)


def test_random_seed_is_sha256_based_and_stable():
    import hashlib
    from reflex_harness.controller import random_seed
    assert random_seed("sem-eval-01", 3) == int(hashlib.sha256(b"sem-eval-01:3").hexdigest()[:16], 16)
    assert random_seed("sem-eval-01", 3) != random_seed("sem-eval-01", 4)


def test_random_arm_is_reproducible_uniform_over_untried_and_logged(monkeypatch):
    from reflex_harness.controller import random_seed
    a, b = _random_row(monkeypatch, 2), _random_row(monkeypatch, 2)
    assert a["chosen_config_id"] == b["chosen_config_id"] and a["random_seed"] == random_seed("sem-eval-01", 2)
    assert a["policy"] == "random" and a["repeat"] == 2 and a["retrieved"] == []
    assert [c["_id"] for c in a["candidates"]] == ["caller", "dependency", "diagnostic"]
    picks = {_random_row(monkeypatch, r)["chosen_config_id"] for r in range(30)}
    assert picks <= {"caller", "dependency", "diagnostic"} and len(picks) >= 2
