"""Solvability dry run (Gate 9, Phase 2): one attempt per task with its designed config, from
the seed, no history, no ladder, verified. Dev evidence that the task is solvable by design —
not an eval result, never re-sampled. Writes results/phase2/dryrun.json.

Usage: python scripts/dry_run.py [task_id ...] [--out NAME]
  default tasks: active tasks added in Gate 9; --out is a path under results/ (default
  phase2/dryrun.json) and is never overwritten
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reflex_harness.config import CONFIGS_R1  # noqa: E402
from reflex_harness.context import pin_focal  # noqa: E402
from reflex_harness.controller import record, run_attempt  # noqa: E402
from reflex_harness.runner import TASKS_DIR, LocalRunner, load_task  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CFG = {c["config_id"]: c for c in CONFIGS_R1}


def one(entry, stamp):
    task = load_task(entry["task_id"])
    runner = LocalRunner()
    run_id = f"dryrun-{task.task_id}-{stamp}"
    ws = runner.prepare(task)
    try:
        base = runner.run(ws, task.diag_cmd, 120)
        pinned = pin_focal(ws, base)
        a = run_attempt(runner, ws, base, CFG[entry["designed_config"]], pinned, [], run_id=run_id,
                        phase="dev", attempt_n=1, verify=True)
        record(a, run_id=run_id, phase="dev", mode="dryrun", task_id=task.task_id, attempt_n=1,
               rolled_back=False)
    finally:
        runner.cleanup(ws)
    return {"task_id": task.task_id, "family": entry["family"], "split": entry["split"],
            "designed_config": entry["designed_config"], "run_id": run_id,
            "outcome": "verified" if a.verified else "diag-only" if a.solved
                       else "regression" if a.regressed else "failed",
            "edited": a.edited, "failing_after": [n.split("::")[-1] for n in a.report.failed],
            "note": a.note, "error": a.error, "cost_usd": round(a.cost_usd, 6)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks", nargs="*")
    ap.add_argument("--out", default="phase2/dryrun.json")
    args = ap.parse_args()
    out = ROOT / "results" / args.out
    if out.exists():
        sys.exit(f"{out} exists; dry runs are never re-sampled or overwritten")
    index = json.loads((TASKS_DIR / "index.json").read_text())["tasks"]
    entries = [e for e in index if (e["task_id"] in args.tasks if args.tasks
                                    else e["added_in"].startswith("gate9") and not e.get("retired"))]
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    with ThreadPoolExecutor(max_workers=len(entries)) as pool:
        results = list(pool.map(lambda e: one(e, stamp), entries))
    for r in results:
        print(f"  {r['task_id']:<12} {r['designed_config']:<10} {r['outcome']:<10} ${r['cost_usd']:.4f}  "
              f"edited={[e.split('::')[-1] for e in r['edited']]}"
              f"{'  failing=' + str(r['failing_after']) if r['failing_after'] else ''}"
              f"{'  ERROR ' + str(r['error'])[:80] if r['error'] else ''}")
    ok = sum(r["outcome"] == "verified" for r in results)
    total = sum(r["cost_usd"] for r in results)
    print(f"\nverified {ok}/{len(results)} with the designed config; cost ${total:.4f}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"stamp": stamp, "results": results,
                                                 "cost_usd": round(total, 6)}, indent=1) + "\n")


if __name__ == "__main__":
    main()
