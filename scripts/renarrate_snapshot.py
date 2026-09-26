"""Re-narrate a snapshot in place: regenerate ONLY failure_narrative and error_symbols.

Attempts, prior_attempts and trial outcomes are untouched. The narrative's fix diff comes
from each checkpoint's own verified trial (root_cause_from) in the `attempts` log, re-verified
first. Model calls: narrator only. Then waits until the new text is embedded and indexed.

Usage: python scripts/renarrate_snapshot.py [--snapshot mem-v1] --reason "..."
"""
import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reflex_harness import config  # noqa: E402
from reflex_harness.context import pin_focal  # noqa: E402
from reflex_harness.jev import diff_excerpt  # noqa: E402
from reflex_harness.narrator import forbidden_tokens, narrate_task, task_symbols  # noqa: E402
from reflex_harness.runner import LocalRunner, load_task  # noqa: E402
from reflex_harness.store import db  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=config.SNAPSHOT_ID)
    ap.add_argument("--reason", required=True)
    args = ap.parse_args()
    ckpt, runner = db()["checkpoints"], LocalRunner()
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    docs = list(ckpt.find({"snapshot_id": args.snapshot}).sort("checkpoint_id", 1))
    for d in docs:
        task = load_task(d["task_id"])
        ws = runner.prepare(task)
        try:
            base = runner.run(ws, task.diag_cmd, 120)
            pinned = pin_focal(ws, base)
        finally:
            runner.cleanup(ws)
        assert (pinned.path, pinned.function) == (d["focal"]["path"], d["focal"]["function"]), d["checkpoint_id"]
        seed = {p: (task.repo / p).read_text() for p in task.allowlist}
        fix = db()["attempts"].find_one(
            {"mode": "build", "task_id": d["task_id"], "attempt_n": 3, "config_id": d["root_cause_from"],
             "verified": True, "created_at": {"$lte": d["created_at"]}}, sort=[("created_at", -1)])
        fixed = {**seed, **{f["path"]: f["content"] for f in fix["patch"]["files"]}}
        vws = runner.prepare(task, state=fixed)
        try:
            still_verified = runner.run(vws, task.diag_cmd, 120).all_pass and runner.verify(vws, 120).all_pass
        finally:
            runner.cleanup(vws)
        if not still_verified:
            sys.exit(f"{d['checkpoint_id']}: the stored verified fix no longer verifies; stopping")
        symbols = task_symbols(pinned.function, base)
        narrative, violations, cost = narrate_task(
            seed, base, pinned.function, diff_excerpt(seed, fixed),
            forbidden_tokens(task.repo, task.allowlist, symbols),
            run_id=f"renarrate-{args.snapshot}-{d['task_id']}-{stamp}", phase="dev", attempt_n=0)
        ckpt.update_one({"_id": d["_id"]}, {"$set": {
            "failure_narrative": narrative, "narrative_violations": violations, "error_symbols": symbols,
            "renarrated": {"at": datetime.now(timezone.utc), "reason": args.reason,
                           "fix_attempt_run_id": fix["run_id"],
                           "previous_narrative": d["failure_narrative"],
                           "previous_error_symbols": d["error_symbols"]}}})
        print(f"\n{d['checkpoint_id']} (fix from {d['root_cause_from']}, run {fix['run_id']}; re-verified) ${cost:.4f}")
        print(f"  old: {d['failure_narrative']}")
        print(f"  new: {narrative}{'  INVALID ' + str(violations) if violations else ''}")
        print(f"  symbols: {d['error_symbols']}  ->  {symbols}")

    # wait until the new narratives are embedded. Voyage embeds documents
    # and queries with different input types, so identical text scores ~0.93-0.95, not 1.0:
    # the discriminating check is that each doc now scores higher for its new text than its old.
    def self_score(q, cid):
        for r in ckpt.aggregate([{"$vectorSearch": {
                "index": config.VECTOR_INDEX, "path": "failure_narrative", "query": q,
                "numCandidates": 20, "limit": 4, "filter": {"snapshot_id": args.snapshot}}},
                {"$project": {"checkpoint_id": 1, "s": {"$meta": "vectorSearchScore"}}}]):
            if r["checkpoint_id"] == cid:
                return r["s"]
        return 0.0

    t0 = time.time()
    while time.time() - t0 < 300:
        fresh = list(ckpt.find({"snapshot_id": args.snapshot}))
        ok_vec = all(self_score(f["failure_narrative"], f["checkpoint_id"])
                     > self_score(f["renarrated"]["previous_narrative"], f["checkpoint_id"]) for f in fresh)
        if ok_vec:
            print(f"\nre-embedded and re-indexed after {time.time() - t0:.0f}s (every doc scores higher for "
                  f"its new narrative than its old one)")
            return
        time.sleep(5)
    sys.exit("timed out waiting for re-embedding / re-indexing")


if __name__ == "__main__":
    main()
