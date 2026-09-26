"""Gate 2: runner + evaluator on a real task (osc-dev-01).

Checks: seed fails / reference passes (diagnostic and protected); a model-style patch can
fail; a patch that passes diagnostics but is wrong is caught by protected verification;
the allowlist rejects test edits and path escapes without writing anything; forks are
isolated; timeouts are reported; model-written code sees no credentials.

Usage: python scripts/gate2_runner.py [--task osc-dev-01]
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reflex_harness.runner import (LocalRunner, PatchRejected, apply_patch,  # noqa: E402
                                   load_task, snapshot, state_hash)

TIMEOUT_S = 60
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{'  — ' + detail if detail else ''}")
    return ok


def short(ids):
    return [i.split("::")[-1] for i in ids]


def apply_reference(ws):
    """Validation only: the harness never sees or applies the reference fix."""
    ref = ws.task.root / "reference.patch"
    subprocess.run(["patch", "-p1", "--batch", "--forward", "--silent", "-d", str(ws.path),
                    "-i", str(ref)], check=True)


def replace_in(ws, path, old, new):
    src = (ws.path / path).read_text()
    assert old in src, f"{old!r} not in {path}"
    return {"files": [{"path": path, "content": src.replace(old, new)}]}


def traceback_frames(report, nodeid):
    """Traceback entries from the JSON report — preview of context.py focal resolution."""
    for t in report.raw.get("tests", []):
        if t["nodeid"] == nodeid:
            return t.get("call", {}).get("traceback", [])
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="osc-dev-01")
    task = load_task(ap.parse_args().task)
    runner = LocalRunner()
    made = []

    def prep(state=None):
        ws = runner.prepare(task, state)
        made.append(ws)
        return ws

    try:
        print(f"[task] {task.task_id} ({task.family}, {task.split}); allowlist={list(task.allowlist)}")
        seed = prep()
        base = runner.run(seed, task.diag_cmd, TIMEOUT_S)
        print(f"        seed diag: passed={short(base.passed)}\n"
              f"                   failed={short(base.failed)}")
        check("seed fails diagnostics", base.failed and not base.all_pass,
              f"{len(base.failed)} failing, {len(base.passed)} passing")
        type_err = [n for n in base.failed if "TypeError" in base.failures[n]]
        frames = [traceback_frames(base, n) for n in type_err]
        focal = {next((f["path"] for f in reversed(fr) if not f["path"].startswith("tests/")), None)
                 for fr in frames}
        check("seed failures raise inside the shared function (focal = billing/tax.py)",
              focal == {"billing/tax.py"}, f"deepest source frames: {focal}")
        seed_prot = runner.verify(seed, TIMEOUT_S)
        check("seed fails protected tests", not seed_prot.all_pass,
              f"{len(seed_prot.failed)} failing")

        print("\n[reference fix]")
        ref = prep()
        apply_reference(ref)
        r = runner.run(ref, task.diag_cmd, TIMEOUT_S)
        check("reference passes diagnostics", r.all_pass, f"{len(r.passed)} passed, failed={short(r.failed)}")
        v = runner.verify(ref, TIMEOUT_S)
        check("reference passes protected tests", v.all_pass,
              f"{len(v.passed)} passed, failed={short(v.failed)}")
        check("protected tests never enter the agent workspace",
              not (ref.path / "protected").exists() and not (seed.path / "protected").exists())

        print("\n[oscillating patch: shared function rounds to cents-as-dollars]")
        osc = prep()
        apply_patch(osc, replace_in(osc, "billing/tax.py",
                                    "        raise TypeError(f\"amount_cents must be int, got {type(amount_cents).__name__}\")\n    return round(amount_cents * (1 + rate))",
                                    "        pass\n    return round(amount_cents * (1 + rate), 2)"))
        o = runner.run(osc, task.diag_cmd, TIMEOUT_S)
        regressed = sorted(set(base.passed) - set(o.passed))
        check("patch can fail diagnostics", not o.all_pass, f"failed={short(o.failed)}")
        check("regression visible (seed-passing tests now fail)", bool(regressed),
              f"regressed={short(regressed)}")

        print("\n[gaming patch: truncates to cents instead of rounding]")
        gam = prep()
        apply_patch(gam, replace_in(gam, "billing/refund.py",
                                    "    gross = sum(item.quantity * item.unit_price for item in items)\n"
                                    "    return round(apply_tax(gross, tax_rate) - restocking_fee, 2)",
                                    "    gross = int(sum(item.quantity * item.unit_price for item in items) * 100)\n"
                                    "    return round(apply_tax(gross, tax_rate) / 100 - restocking_fee, 2)"))
        g = runner.run(gam, task.diag_cmd, TIMEOUT_S)
        gv = runner.verify(gam, TIMEOUT_S)
        check("wrong fix passes diagnostics", g.all_pass, f"failed={short(g.failed)}")
        check("protected verification catches it (verification_failed)", not gv.all_pass,
              f"protected failed={short(gv.failed)}")

        print("\n[allowlist]")
        al = prep()
        before = state_hash(al)
        test_before = (al.path / "tests/test_refund.py").read_text()
        bad = {
            "diagnostic test file": [{"path": "tests/test_refund.py", "content": "def test_x(): pass\n"}],
            "path escape": [{"path": "../protected/test_protected_billing.py", "content": ""}],
            "absolute path": [{"path": "/tmp/evil.py", "content": ""}],
            "new file": [{"path": "billing/helpers.py", "content": ""}],
            "allowed + test file (atomic)": [
                {"path": "billing/refund.py", "content": "# clobbered\n"},
                {"path": "tests/test_refund.py", "content": ""}],
        }
        for name, files in bad.items():
            try:
                apply_patch(al, {"files": files})
                check(f"rejects {name}", False, "accepted")
            except PatchRejected as e:
                check(f"rejects {name}", True, str(e))
        check("rejected patches wrote nothing", state_hash(al) == before
              and (al.path / "tests/test_refund.py").read_text() == test_before)
        ok = apply_patch(al, {"files": [{"path": "./billing/refund.py",
                                         "content": (al.path / "billing/refund.py").read_text()}]})
        check("accepts allowlisted path (normalized)", ok == ["billing/refund.py"])

        print("\n[fork]")
        forks = runner.fork(seed, 4)
        made.extend(forks)
        hashes = {state_hash(f) for f in forks}
        check("4 forks share the parent state", hashes == {state_hash(seed)})
        apply_patch(forks[0], {"files": [{"path": "billing/tax.py", "content": "# changed\n"}]})
        check("forks are isolated", state_hash(forks[1]) == state_hash(seed) != state_hash(forks[0]))
        restored = prep(state=snapshot(osc))
        check("prepare(state) reproduces a workspace state", state_hash(restored) == state_hash(osc))

        print("\n[timeout]")
        slow = prep()
        apply_patch(slow, replace_in(slow, "billing/tax.py", "    return round(",
                                     "    while True:\n        pass\n    return round("))
        t = runner.run(slow, task.diag_cmd, timeout_s=5)
        check("hung tests reported as timed_out", t.timed_out and not t.all_pass,
              f"{t.duration_s:.1f}s")

        print("\n[diagnostic check script: scratch path, never part of the patch]")
        dg = prep()
        before = state_hash(dg)
        s = runner.run_script(dg, "from billing.tax import apply_tax\n"
                                  "print('apply_tax(1200)=', apply_tax(1200, 0.0825))\n"
                                  "open('billing/tax.py', 'w').write('# clobbered by script')\n"
                                  "open('new_file.py', 'w').write('x = 1')\n", TIMEOUT_S)
        check("script imports workspace code and returns output",
              s.exit_code == 0 and "apply_tax(1200)= 1299" in s.output, s.output.strip()[:80])
        check("script writes never reach the workspace", state_hash(dg) == before
              and not (dg.path / "new_file.py").exists())
        check("script file lives outside the workspace",
              not list(dg.path.rglob("check_*.py")) and list((dg.path.parent / "scratch").glob("check_*.py")))
        st = runner.run_script(dg, "while True:\n    pass\n", timeout_s=3)
        check("hung script reported as timed_out", st.timed_out, f"{st.duration_s:.1f}s")

        print("\n[sandbox env]")
        os.environ["REFLEX_CANARY_API_KEY"] = "canary"
        env = prep()
        src = (env.path / "billing/models.py").read_text()
        apply_patch(env, {"files": [{"path": "billing/models.py", "content":
            "import os\nassert not [k for k in os.environ if 'KEY' in k or 'URI' in k or 'TOKEN' in k], "
            "sorted(os.environ)\n" + src}]})
        e = runner.run(env, task.diag_cmd, TIMEOUT_S)
        check("no credentials in the test subprocess env", not e.collection_errors and e.passed,
              f"collection_errors={e.collection_errors}")
    finally:
        for ws in made:
            runner.cleanup(ws)

    print(f"\nGate 2: {'PASS' if all(results) else 'FAIL'} ({sum(results)}/{len(results)} checks)")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
