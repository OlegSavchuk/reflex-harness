import dataclasses
import json
import textwrap

import pytest

from reflex_harness.config import CONFIGS_R1
from reflex_harness.context import (ContextError, build_context, pin_focal, render,
                                    resolve_dependencies, resolve_focal)
from reflex_harness.runner import LocalRunner, Task, TestReport, Workspace, load_task

CFG = {c["config_id"]: c for c in CONFIGS_R1}
GOAL = "Make the failing tests pass."


@pytest.fixture(scope="module")
def seed():
    runner = LocalRunner()
    task = load_task("osc-dev-01")
    ws = runner.prepare(task)
    report = runner.run(ws, task.diag_cmd, 60)
    yield ws, report
    runner.cleanup(ws)


@pytest.fixture(scope="module")
def pinned(seed):
    return pin_focal(*seed)


def prompt(ws, report, config_id):
    ctx = build_context(ws, report, CFG[config_id], pin_focal(ws, report))
    return ctx, render(ctx, GOAL, [])[1]["content"]


def test_focal_from_traceback(seed):
    ws, report = seed
    site, source = resolve_focal(ws, report)
    assert (site.path, site.name, source) == ("billing/tax.py", "apply_tax", "traceback")


def test_focused_has_no_caller_code_or_frames(seed):
    ws, report = seed
    ctx, text = prompt(ws, report, "focused")
    assert list(ctx.files) == ["billing/tax.py"]
    for leak in ("billing/refund.py", "billing/invoice.py", "refund_total_dollars", "def refund",
                 "where 13.0"):
        assert leak not in text, leak
    assert "TypeError: amount_cents must be int, got float" in text
    assert "at billing/tax.py:7 in apply_tax" in text
    assert "test_refund_integer_dollar_prices" in text   # test names are allowed


def test_caller_sees_callers_and_full_traceback(seed):
    ws, report = seed
    ctx, text = prompt(ws, report, "caller")
    assert {s.name for s in ctx.callers} == {"invoice_total_cents", "refund_total_dollars"}
    assert list(ctx.files) == ["billing/tax.py", "billing/invoice.py", "billing/refund.py"]
    assert "billing/refund.py:9: in refund_total_dollars" in text   # full traceback
    assert "def refund_summary" in text                              # whole caller file


def test_dependency_gets_full_traceback_but_no_project_deps_here(seed):
    ws, report = seed
    ctx, text = prompt(ws, report, "dependency")
    assert ctx.deps == []          # apply_tax calls only builtins
    assert ctx.full_traceback and "billing/refund.py:9" in text


def test_four_configs_render_distinct_prompts(seed):
    ws, report = seed
    texts = {c: prompt(ws, report, c)[1] for c in ("focused", "caller", "dependency")}
    ctx = build_context(ws, report, CFG["diagnostic"], pin_focal(ws, report))
    check_msgs = render(ctx, GOAL, [], step="check")
    patch_msgs = render(ctx, GOAL, [], step="patch", check=("print(1)", "1"))
    texts["diagnostic/check"] = check_msgs[0]["content"] + check_msgs[1]["content"]
    texts["diagnostic/patch"] = patch_msgs[1]["content"]
    assert len(set(texts.values())) == 5
    assert "ITS OUTPUT\n1" in texts["diagnostic/patch"]
    assert "billing/refund.py" not in texts["diagnostic/patch"]


def test_manifest_fallback(seed, tmp_path):
    ws, _ = seed
    root = tmp_path / "task"
    root.mkdir()
    (root / "context_manifest.json").write_text(
        json.dumps({"focal": {"path": "billing/refund.py", "function": "refund_total_dollars"}}))
    task = dataclasses.replace(ws.task, root=root)
    no_frames = TestReport(passed=[], failed=["tests/t.py::test_x"], skipped=[], collection_errors=[],
                           failures={}, exit_code=1, duration_s=0.0, raw={"tests": [
                               {"nodeid": "tests/t.py::test_x", "outcome": "failed",
                                "call": {"outcome": "failed", "traceback": [
                                    {"path": "tests/t.py", "lineno": 3, "message": "AssertionError"}]}}]})
    site, source = resolve_focal(Workspace(task, ws.path), no_frames)
    assert (site.name, source) == ("refund_total_dollars", "manifest")
    with pytest.raises(ContextError):
        resolve_focal(Workspace(dataclasses.replace(ws.task, root=tmp_path), ws.path), no_frames)


def test_dependencies_resolve_helpers_and_annotated_types(tmp_path):
    (tmp_path / "shop").mkdir()
    files = {
        "shop/models.py": "from dataclasses import dataclass\n\n@dataclass\nclass Cart:\n    items: list\n",
        "shop/money.py": "def round_money(x):\n    return round(x, 2)\n",
        "shop/cart.py": textwrap.dedent("""\
            from shop.models import Cart
            from shop.money import round_money

            def cart_total(cart: Cart) -> float:
                return round_money(sum(cart.items))
            """),
    }
    for p, c in files.items():
        (tmp_path / p).write_text(c)
    task = Task("syn", "semantic_repetition", "dev", "", tuple(files), (), (), tmp_path)
    ws = Workspace(task, tmp_path)
    from reflex_harness.context import find_def
    deps = resolve_dependencies(ws, find_def(ws, "cart_total"))
    assert {(d.path, d.name) for d in deps} == {("shop/money.py", "round_money"),
                                                 ("shop/models.py", "Cart")}


def test_pinned_focal_survives_drift_and_re_resolves_when_gone(seed, pinned):
    ws, report = seed
    runner = LocalRunner()
    drifted = runner.fork(ws, 1)[0]
    try:
        tax = drifted.path / "billing/tax.py"
        # oscillating edit: apply_tax returns floats, format_cents crashes downstream
        tax.write_text(tax.read_text().replace("raise TypeError", "pass  # ").replace(
            "round(amount_cents * (1 + rate))", "round(amount_cents * (1 + rate), 2)"))
        r = runner.run(drifted, ws.task.diag_cmd, 60)
        assert resolve_focal(drifted, r)[0].name == "format_cents"      # per-attempt would drift
        ctx = build_context(drifted, r, CFG["focused"], pinned)
        assert (ctx.focal.name, ctx.focal_source) == ("apply_tax", "traceback")
        tax.write_text(tax.read_text().replace("def apply_tax", "def add_tax") + "\napply_tax = add_tax\n")
        ctx = build_context(drifted, runner.run(drifted, ws.task.diag_cmd, 60), CFG["focused"], pinned)
        assert (ctx.focal.name, ctx.focal_source) == ("format_cents", "re-resolved")
    finally:
        runner.cleanup(drifted)


def test_edited_functions():
    from reflex_harness.context import edited_functions
    before = {"m.py": "import os\n\ndef f():\n    return 1\n\ndef g():\n    return 2\n"}
    after = {"m.py": "import os\n\ndef f():\n    return 1\n\ndef g():\n    return 3\n"}
    assert edited_functions(before, after) == ["m.py::g"]
    assert edited_functions(before, before) == []
    assert "m.py::<module>" in edited_functions(before, {"m.py": "import sys\n" + before["m.py"][10:]})
