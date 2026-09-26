"""Gate 3: the same state rendered under all 4 configs gives visibly different prompts.

Two states of osc-dev-01: the seed and a checkpoint-like state after an oscillating edit.
The focal is pinned once from the seed baseline and reused for both states. The diagnostic
config's check script runs through the runner's scratch path. Full prompts are written to
runs/gate3/<state>/<config>.md for inspection. No model calls.

Usage: python scripts/gate3_context.py [--task osc-dev-01]
"""
import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reflex_harness.config import CONFIGS_R1  # noqa: E402
from reflex_harness.context import build_context, pin_focal, render  # noqa: E402
from reflex_harness.runner import LocalRunner, apply_patch, load_task  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "runs" / "gate3"
CHECK_SCRIPT = ("from billing.tax import apply_tax\n"
                "for v in (1200, 2498):\n"
                "    print(v, '->', apply_tax(v, 0.0825))\n")
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{'  — ' + detail if detail else ''}")
    return ok


def oscillating_patch(ws):
    src = (ws.path / "billing/tax.py").read_text()
    return {"files": [{"path": "billing/tax.py", "content": src.replace(
        '        raise TypeError(f"amount_cents must be int, got {type(amount_cents).__name__}")\n'
        "    return round(amount_cents * (1 + rate))",
        "        pass\n    return round(amount_cents * (1 + rate), 2)")}]}


PRIOR = [
    "Attempt 1 (focused): edited billing/tax.py — accepted non-int amounts and rounded to "
    "2 decimals. Refund tests passed; test_invoice_total_cents and test_invoice_summary failed "
    "(regression, rolled back).",
    "Attempt 2 (focused): edited billing/tax.py — same change with a float cast. Same two "
    "invoice tests failed.",
]


def render_all(runner, ws, report, task, prior, pinned):
    prompts, ctxs = {}, {}
    for cfg in CONFIGS_R1:
        ctx = build_context(ws, report, cfg, pinned)
        ctxs[cfg["config_id"]] = ctx
        if cfg["workflow"]["diagnostic_first"]:
            m1 = render(ctx, task.goal, prior, step="check")
            res = runner.run_script(ws, CHECK_SCRIPT, 30)
            m2 = render(ctx, task.goal, prior, step="patch", check=(CHECK_SCRIPT, res.output))
            prompts["diagnostic/1-check"] = m1
            prompts["diagnostic/2-patch"] = m2
        else:
            prompts[cfg["config_id"]] = render(ctx, task.goal, prior)
    return prompts, ctxs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="osc-dev-01")
    task = load_task(ap.parse_args().task)
    runner = LocalRunner()
    made = []
    try:
        seed = runner.prepare(task)
        made.append(seed)
        osc = runner.prepare(task)
        made.append(osc)
        apply_patch(osc, oscillating_patch(osc))
        states = {"seed": (seed, []), "after-oscillation": (osc, PRIOR)}
        pinned = pin_focal(seed, runner.run(seed, task.diag_cmd, 60))
        print(f"[pinned focal] {pinned.path}::{pinned.function} (source={pinned.source}), "
              f"from the seed baseline; reused for every state and config")

        for state, (ws, prior) in states.items():
            report = runner.run(ws, task.diag_cmd, 60)
            prompts, ctxs = render_all(runner, ws, report, task, prior, pinned)
            focal = ctxs["focused"]
            print(f"\n[{state}] failing={[n.split('::')[-1] for n in report.failed]}")
            print(f"        focal={focal.focal.path}::{focal.focal.name} (source={focal.focal_source})")
            print(f"        {'config':<19} {'files shown':<52} {'callers':>7} {'deps':>4} "
                  f"{'traceback':>9} {'chars':>6}  sha")
            outdir = OUT / state
            outdir.mkdir(parents=True, exist_ok=True)
            for name, msgs in prompts.items():
                ctx = ctxs[name.split("/")[0]]
                text = "\n\n".join(f"## {m['role']}\n\n{m['content']}" for m in msgs)
                (outdir / f"{name.replace('/', '_')}.md").write_text(text)
                print(f"        {name:<19} {', '.join(ctx.files):<52} {len(ctx.callers):>7} "
                      f"{len(ctx.deps):>4} {'full' if ctx.full_traceback else 'filtered':>9} "
                      f"{len(text):>6}  {hashlib.sha256(text.encode()).hexdigest()[:8]}")
            user = {n: m[1]["content"] for n, m in prompts.items()}
            everything = {n: m[0]["content"] + m[1]["content"] for n, m in prompts.items()}
            check("5 distinct prompts (4 configs, diagnostic has 2 calls)",
                  len(set(everything.values())) == 5)
            fc = focal.focal
            others = [f for f in task.allowlist if f != fc.path]
            for n in ("focused", "diagnostic/1-check", "diagnostic/2-patch"):
                ctx = ctxs[n.split("/")[0]]
                body = user[n]
                for line in prior:  # the model's own history may name files it edited
                    body = body.replace(line, "")
                leaks = [f for f in others if f in body]
                check(f"{n}: only the focal file, filtered traceback",
                      list(ctx.files) == [fc.path] and not ctx.full_traceback and not leaks,
                      f"leaks={leaks}" if leaks else "")
            callers = ctxs["caller"].callers
            check("caller: every caller file shown in full, full traceback",
                  bool(callers) and all(c.path in ctxs["caller"].files for c in callers)
                  and ctxs["caller"].full_traceback,
                  f"callers of {fc.name}: {[c.name for c in callers]}")
            check("dependency: full traceback", ctxs["dependency"].full_traceback,
                  f"deps of {fc.name}: {[d.name for d in ctxs['dependency'].deps]}")
            check("diagnostic: check output reaches the patch call",
                  "ITS OUTPUT\n1200 -> 1299" in user["diagnostic/2-patch"])
            check("prior attempts included", all(p in user["focused"] for p in prior))
            check("focal_source recorded", focal.focal_source in ("traceback", "manifest"),
                  f"{fc.path}::{fc.name} via {focal.focal_source}")
            check("focal is the pinned shared function in every state (no drift)",
                  (fc.path, fc.name) == ("billing/tax.py", "apply_tax"), f"{fc.path}::{fc.name}")
    finally:
        for ws in made:
            runner.cleanup(ws)

    print(f"\nprompts written to {OUT.relative_to(Path.cwd()) if OUT.is_relative_to(Path.cwd()) else OUT}")
    print(f"Gate 3: {'PASS' if all(results) else 'FAIL'} ({sum(results)}/{len(results)} checks)")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
