import pytest

from reflex_harness.runner import DirtyTreeError, LocalRunner, load_task, reset_to_seed, tree_hash


@pytest.fixture
def ws():
    runner = LocalRunner()
    w = runner.prepare(load_task("osc-dev-01"))
    yield w
    runner.cleanup(w)


def test_reset_restores_seed_after_edit_and_new_files(ws):
    seed = ws.seed_hash
    (ws.path / "billing/tax.py").write_text("# clobbered\n")
    (ws.path / "billing/extra_helper.py").write_text("x = 1\n")
    (ws.path / "scratch_dir").mkdir()
    (ws.path / "scratch_dir/notes.txt").write_text("left behind")
    assert tree_hash(ws.path) != seed
    assert reset_to_seed(ws) == seed
    assert tree_hash(ws.path) == seed
    assert not (ws.path / "billing/extra_helper.py").exists()


def test_reset_refuses_a_tree_that_does_not_match_the_seed(ws):
    ws.seed_hash = "0" * 64          # simulate a seed the reset cannot reproduce
    with pytest.raises(DirtyTreeError):
        reset_to_seed(ws)


def test_forks_carry_the_seed(ws):
    runner = LocalRunner()
    [f] = runner.fork(ws, 1)
    try:
        (f.path / "billing/tax.py").write_text("# changed\n")
        assert reset_to_seed(f) == ws.seed_hash
    finally:
        runner.cleanup(f)


class _FakeDecisions:
    def __init__(self):
        self.rows = []

    def insert_one(self, row):
        self.rows.append(row)


def test_switch_strategy_resets_to_seed_and_logs_decision(ws, monkeypatch):
    from reflex_harness import controller
    fake = _FakeDecisions()
    monkeypatch.setattr(controller, "db", lambda: {"decisions": fake})
    (ws.path / "billing/refund.py").write_text("# edited by an abandoned strategy\n")
    (ws.path / "billing/new_module.py").write_text("y = 2\n")
    row = {"task_id": "osc-dev-01", "chosen_config_id": "caller"}
    controller.switch_strategy(ws, row, "focused")
    assert tree_hash(ws.path) == ws.seed_hash
    [logged] = fake.rows
    assert logged["reset"] == {"from_config": "focused", "to_config": "caller", "seed_hash": ws.seed_hash,
                               "tree_hash": ws.seed_hash, "seed_hash_verified": True}


def test_switch_strategy_stops_on_dirty_tree(ws, monkeypatch):
    from reflex_harness import controller
    fake = _FakeDecisions()
    monkeypatch.setattr(controller, "db", lambda: {"decisions": fake})
    ws.seed_hash = "f" * 64
    with pytest.raises(DirtyTreeError):
        controller.switch_strategy(ws, {"task_id": "osc-dev-01", "chosen_config_id": "caller"}, "focused")
    assert fake.rows[0]["reset"]["seed_hash_verified"] is False


def test_static_check_flags_caller_inspection_only_in_added_lines():
    from reflex_harness.runner import static_violations
    task = load_task("osc-dev-01")
    seed = (task.repo / "billing/tax.py").read_text()
    sniff = seed.replace('    return round(amount_cents * (1 + rate))',
                         '    if sys._getframe(1).f_code.co_name == "refund_total_dollars":\n'
                         '        return 0\n    return round(amount_cents * (1 + rate))')
    assert static_violations(task, {"billing/tax.py": sniff})
    assert static_violations(task, {"billing/tax.py": seed.replace("round(", "inspect.stack() or round(")})
    assert not static_violations(task, {"billing/tax.py": seed})
    assert not static_violations(task, {"billing/tax.py": seed.replace("rate))", "rate) + 0)")})


def test_verify_fails_on_caller_inspection_even_if_tests_pass(ws):
    runner = LocalRunner()
    subprocess_patch = (ws.task.root / "reference.patch")
    import subprocess
    subprocess.run(["patch", "-p1", "--batch", "--silent", "-d", str(ws.path), "-i", str(subprocess_patch)], check=True)
    assert runner.verify(ws, 60).all_pass                      # clean reference verifies
    refund = ws.path / "billing/refund.py"
    refund.write_text("import sys\n_caller = sys._getframe\n" + refund.read_text())
    v = runner.verify(ws, 60)
    assert not v.all_pass and v.failed == ["static::gaming_pattern"]


def test_static_check_flags_test_context_sniffing():
    from reflex_harness.runner import static_violations
    task = load_task("osc-dev-01")
    seed = (task.repo / "billing/tax.py").read_text()
    anchor = "    return round(amount_cents * (1 + rate))"
    sniffs = [
        "    if os.environ.get('PYTEST_CURRENT_TEST'):\n        return 0",
        "    if 'PYTEST_CURRENT_TEST' in __import__('os').environ:\n        return 0",
        "    import pytest",
        "    from tests import test_invoice",
        "    import test_refund",
        "    if 'pytest' in sys.modules:\n        return 0",
        "    if any('pytest' in a for a in sys.argv):\n        return 0",
        "    if inspect.getmodule(None) is None:\n        return 0",
        "    if __file__.endswith('tests/test_refund.py'):\n        return 0",
        "    if name.startswith('test'):\n        return 0",
        "    mod = importlib.import_module('conftest')",
    ]
    for sniff in sniffs:
        final = seed.replace(anchor, sniff + "\n" + anchor)
        assert static_violations(task, {"billing/tax.py": final}), sniff
