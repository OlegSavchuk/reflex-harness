"""Gate 6: build development memory (SPEC §9.3) into a frozen snapshot.

Per dev task: up to two `focused` attempts from the seed (rollback on regression; a diagnostics
pass ends the history, which is then the failed attempts before it, possibly none: a pass at
attempt 1 gives an empty history, policy since 2026-09-26), then reset to the
seed (same reset + seed-hash assert as a strategy switch) -> fork 4 -> one trial per config,
concurrently, from the seed, with identical prior_attempts and the reset line; each outcome
records solved and verified. The narrative is built from the task (seed code, seed failing
tests, the verified fix's diff), never from the agent's attempts; error_symbols from the seed
baseline. Checkpoints are inserted after all four trials finish, then polled until searchable.
Every model call writes a `calls` row; every attempt writes an `attempts` row (mode "build").

Usage: python scripts/build_memory.py [--snapshot mem-v1] [--force]
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reflex_harness import config  # noqa: E402
from reflex_harness.context import locate_focal, pin_focal, resolve_callers  # noqa: E402
from reflex_harness.controller import record, restore, run_attempt, summarize  # noqa: E402
from reflex_harness.jev import diff_excerpt  # noqa: E402
from reflex_harness.narrator import forbidden_tokens, narrate_task, task_symbols  # noqa: E402
from reflex_harness.runner import LocalRunner, load_task, reset_to_seed, task_ids  # noqa: E402
from reflex_harness.store import db  # noqa: E402

CFG = {c["config_id"]: c for c in config.CONFIGS_R1}
OUT = Path(__file__).resolve().parents[1] / "runs" / "memory"


def trial(runner, ws, report, cfg, pinned, prior, run_id):
    for attempt in range(2):  # infra error = missing evidence: retry once, never count as failure
        [fork] = runner.fork(ws, 1)
        try:
            a = run_attempt(runner, fork, report, cfg, pinned, prior, run_id=f"{run_id}-trial-{cfg['config_id']}",
                            phase="dev", attempt_n=3, verify=True, reset_note=bool(prior))
        finally:
            runner.cleanup(fork)
        if not a.infra_error:
            return a
    return a


def build_checkpoint(task_id, snapshot, stamp):
    task = load_task(task_id)
    runner = LocalRunner()
    run_id = f"build-{snapshot}-{task_id}-{stamp}"
    ws = runner.prepare(task)
    try:
        base = runner.run(ws, task.diag_cmd, 120)
        pinned = pin_focal(ws, base)
        prior, cur, touched = [], base, set()
        for n in (1, 2):
            a = run_attempt(runner, ws, cur, CFG["focused"], pinned, prior, run_id=run_id,
                            phase="dev", attempt_n=n, verify=True)
            rolled = bool(a.regressed)
            record(a, run_id=run_id, phase="dev", mode="build", task_id=task_id, attempt_n=n,
                   rolled_back=rolled)
            if a.infra_error:
                return {"task_id": task_id, "error": a.error}
            if a.solved:
                # Build policy (SPEC §9.3): a diagnostics pass ends the history; the checkpoint's
                # history is the failed attempts before it, empty if the pass came at attempt 1
                # (the four trials start from the seed either way). Protected results never feed
                # the loop, so a hack that passes diagnostics is treated as the eval loop sees it.
                break
            touched |= {e.split("::")[0] for e in a.edited}
            prior.append(summarize(n, a, rolled))
            if rolled:
                restore(ws, a.parent_files)
            else:
                cur = a.report

        reset_to_seed(ws)  # abandoned strategy: same reset + seed-hash assert as a switch
        with ThreadPoolExecutor(max_workers=4) as pool:
            trials = list(pool.map(lambda c: trial(runner, ws, base, CFG[c], pinned, prior, run_id),
                                   [c["config_id"] for c in config.CONFIGS_R1]))
        seed_files = {p: (task.repo / p).read_text() for p in task.allowlist}
        fix = next((t for t in trials if t.verified), None)  # registry order
        symbols = task_symbols(pinned.function, base)
        narrative, violations, narr_cost = narrate_task(
            seed_files, base, pinned.function, diff_excerpt(seed_files, fix.files) if fix else None,
            forbidden_tokens(task.repo, task.allowlist, symbols), run_id=run_id, phase="dev",
            attempt_n=3)
        for t in trials:
            record(t, run_id=f"{run_id}-trial-{t.config_id}", phase="dev", mode="build",
                   task_id=task_id, attempt_n=3, rolled_back=False)
        outcomes = [{"config_id": t.config_id, "solved": t.solved, "verified": t.verified,
                     "regression": bool(t.regressed), "cost_usd": round(t.cost_usd, 6)}
                    for t in trials if not t.infra_error]
        site, _ = locate_focal(ws, pinned, base)
        doc = {
            "checkpoint_id": f"{snapshot}-{task_id}", "snapshot_id": snapshot, "family": task.family,
            "task_id": task_id, "failure_narrative": narrative, "narrative_violations": violations,
            "error_symbols": symbols, "focal": pinned.as_doc(),
            "root_cause_from": fix.config_id if fix else None,
            "facets": {"callers_of_focal": len(resolve_callers(ws, site)), "files_touched": len(touched)},
            "compat": {"language": "python", "protocol": config.PROTOCOL, "registry": config.REGISTRY},
            "prior_attempts": prior, "outcomes": outcomes,
            "build_cost_usd": round(narr_cost + sum(t.cost_usd for t in trials), 6),
            "created_at": datetime.now(timezone.utc)}
        db()["checkpoints"].replace_one({"checkpoint_id": doc["checkpoint_id"]}, doc, upsert=True)
        return {"task_id": task_id, "doc": doc,
                "missing": [t.config_id for t in trials if t.infra_error],
                "trial_notes": {t.config_id: t.note or t.error for t in trials}}
    finally:
        runner.cleanup(ws)


def wait_searchable(snapshot, n, timeout_s=300):
    ckpt = db()["checkpoints"]
    vec = [{"$vectorSearch": {"index": config.VECTOR_INDEX, "path": "failure_narrative", "query": "agent",
                              "numCandidates": 50, "limit": 20, "filter": {"snapshot_id": snapshot}}},
           {"$count": "n"}]
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if next(ckpt.aggregate(vec), {"n": 0})["n"] == n:
            return True, time.time() - t0
        time.sleep(5)
    return False, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=config.SNAPSHOT_ID)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    ckpt = db()["checkpoints"]
    existing = ckpt.count_documents({"snapshot_id": args.snapshot})
    if existing and not args.force:
        sys.exit(f"snapshot {args.snapshot} already has {existing} checkpoints (frozen); use --force to rebuild")
    if existing:
        ckpt.delete_many({"snapshot_id": args.snapshot})
    dev = task_ids("dev")
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    print(f"[build] snapshot={args.snapshot} dev tasks={dev}", flush=True)
    with ThreadPoolExecutor(max_workers=len(dev)) as pool:
        results = list(pool.map(lambda t: build_checkpoint(t, args.snapshot, stamp), dev))

    built = [r for r in results if "doc" in r]
    ok, secs = wait_searchable(args.snapshot, len(built)) if built else (False, 0)
    total = 0.0
    for r in results:
        if "doc" not in r:
            print(f"\n{r['task_id']}: NO CHECKPOINT — {r['error']}")
            continue
        d = r["doc"]
        total += d["build_cost_usd"]
        print(f"\n{d['checkpoint_id']} ({d['family']}) focal={d['focal']['function']} ({d['focal']['source']})")
        print(f"  narrative{' (INVALID: ' + '; '.join(d['narrative_violations']) + ')' if d['narrative_violations'] else ''}: {d['failure_narrative']}")
        print(f"  symbols: {d['error_symbols']}")
        for o in d["outcomes"]:
            tag = "VERIFIED" if o["verified"] else "diag-only" if o["solved"] else "regression" if o["regression"] else "failed"
            print(f"  {o['config_id']:<11} {tag:<10} ${o['cost_usd']:.4f}  {(r['trial_notes'].get(o['config_id']) or '')[:90]}")
        if r["missing"]:
            print(f"  missing evidence (infra): {r['missing']}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{args.snapshot}-{stamp}.json").write_text(json.dumps(results, indent=1, default=str))
    print(f"\n{len(built)}/{len(dev)} checkpoints in {args.snapshot}; searchable={ok} ({secs:.0f}s); "
          f"trial+narrator cost ${total:.4f}")
    sys.exit(0 if ok and len(built) == len(dev) else 1)


if __name__ == "__main__":
    main()
