"""Model calibration (Gate 4): one attempt from the seed, N runs per config.

Each run: pinned focal from the seed baseline -> prompt for the config -> one model call ->
apply patch (allowlist) -> diagnostics -> protected verification if diagnostics pass.
Every model call writes a `calls` row (phase "dev"). Patches and results are saved to
runs/calibration/<task>/ for inspection.

Usage: python scripts/calibrate.py --task osc-dev-01 --configs focused caller --n 3
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reflex_harness import agent  # noqa: E402
from reflex_harness.config import CONFIGS_R1  # noqa: E402
from reflex_harness.context import build_context, pin_focal, render  # noqa: E402
from reflex_harness.runner import LocalRunner, PatchRejected, apply_patch, load_task  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "runs" / "calibration"
TIMEOUT_S = 120
CFG = {c["config_id"]: c for c in CONFIGS_R1}


def one_run(runner, task, baseline, pinned, config_id, i, stamp):
    run_id = f"calib-{task.task_id}-{config_id}-{i}-{stamp}"
    ws = runner.prepare(task)
    try:
        ctx = build_context(ws, baseline, CFG[config_id], pinned)
        reply = agent.call(render(ctx, task.goal, []), run_id=run_id, phase="dev", attempt_n=1)
        res = {"run_id": run_id, "config": config_id, "cost_usd": reply.cost_usd,
               "tokens": [reply.input_tokens, reply.output_tokens], "latency_ms": reply.latency_ms,
               "model_reported": reply.model_reported, "note": (reply.data or {}).get("note"),
               "files": [f.get("path") for f in (reply.data or {}).get("files", [])],
               "error": reply.error, "solved": False, "verified": False, "regressed": [],
               "failed": None, "outcome": "error"}
        if reply.data is None:
            return res
        try:
            apply_patch(ws, reply.data)
        except (PatchRejected, KeyError, TypeError) as e:
            res.update(outcome="rejected", error=f"{type(e).__name__}: {e}")
            return res
        rep = runner.run(ws, task.diag_cmd, TIMEOUT_S)
        res["failed"] = [n.split("::")[-1] for n in rep.failed + rep.collection_errors]
        res["regressed"] = sorted(n.split("::")[-1] for n in set(baseline.passed) - set(rep.passed))
        res["solved"] = rep.all_pass
        if rep.all_pass:
            res["verified"] = runner.verify(ws, TIMEOUT_S).all_pass
        res["outcome"] = ("verified" if res["verified"] else "diag-only" if res["solved"]
                          else "regression" if res["regressed"] else "failed")
        res["patch"] = reply.data
        return res
    finally:
        runner.cleanup(ws)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="osc-dev-01")
    ap.add_argument("--configs", nargs="+", default=["focused", "caller"])
    ap.add_argument("--n", type=int, default=3)
    args = ap.parse_args()
    if "diagnostic" in args.configs:
        sys.exit("diagnostic needs the two-call workflow (controller); not calibrated here")
    task = load_task(args.task)
    runner = LocalRunner()
    seed = runner.prepare(task)
    baseline = runner.run(seed, task.diag_cmd, TIMEOUT_S)
    pinned = pin_focal(seed, baseline)
    runner.cleanup(seed)
    print(f"[{task.task_id}] baseline failing={len(baseline.failed)} "
          f"pinned focal={pinned.path}::{pinned.function} ({pinned.source})")

    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    jobs = [(c, i) for c in args.configs for i in range(1, args.n + 1)]
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        results = list(pool.map(lambda j: one_run(runner, task, baseline, pinned, *j, stamp), jobs))

    out = OUT / task.task_id
    out.mkdir(parents=True, exist_ok=True)
    for r in results:
        (out / f"{r['run_id']}.json").write_text(json.dumps(r, indent=2))
        print(f"  {r['config']:<10} #{r['run_id'].split('-')[-2]}  {r['outcome']:<10} "
              f"files={r['files']} failed={r['failed']} regressed={r['regressed']} "
              f"${r['cost_usd']:.4f} {r['tokens'][0]}/{r['tokens'][1]}tok {r['latency_ms'] / 1000:.0f}s"
              f"{'  ERROR ' + r['error'] if r['error'] and r['outcome'] in ('error', 'rejected') else ''}")
        if r["note"]:
            print(f"             note: {r['note'][:150]}")
    print()
    total = 0.0
    for c in args.configs:
        rs = [r for r in results if r["config"] == c]
        cost = sum(r["cost_usd"] for r in rs)
        total += cost
        print(f"  {c:<10} verified {sum(r['verified'] for r in rs)}/{len(rs)}  "
              f"diag-solved {sum(r['solved'] for r in rs)}/{len(rs)}  "
              f"regressions {sum(bool(r['regressed']) for r in rs)}/{len(rs)}  cost ${cost:.4f}")
    print(f"  total cost ${total:.4f}; results in {out}")


if __name__ == "__main__":
    main()
