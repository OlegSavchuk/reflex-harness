"""Leave-one-out retrieval on dev tasks (eval-free preview of neighbourhood quality).

For each dev task: its stored query (tasks/<id>/query.json) runs through the semantic
$vectorSearch stage with the task's own checkpoint excluded. Reports top-1/top-2 with
families, semantic scores and the margin, plus every other checkpoint's score.
The own checkpoint is excluded after the search stage (`_id` is not an indexed filter field);
exact as long as the search limit covers the whole snapshot.

Also reports top-1 same-family rate per family, the margin distribution (min/median/max), and for
counter-pattern dev tasks (SPEC §13.6) whether the top-1 checkpoint is itself a counter pattern.
A dev task without a checkpoint in the snapshot is queried against all of it. Report only: no
tuning. Writes results/phase5/loo-<snapshot>.json.

Usage: python scripts/loo_retrieval.py [--snapshot mem-v1]
"""
import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reflex_harness import config  # noqa: E402
from reflex_harness.pipelines import _vector_search  # noqa: E402
from reflex_harness.queries import load_query, query_input  # noqa: E402
from reflex_harness.runner import load_task, task_ids  # noqa: E402
from reflex_harness.store import db  # noqa: E402
from reflex_harness.task_index import is_counter_pattern, load_index  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=config.SNAPSHOT_ID)
    snapshot = ap.parse_args().snapshot
    ckpt = db()["checkpoints"]
    n_snapshot = ckpt.count_documents({"snapshot_id": snapshot})
    dev = task_ids("dev")
    index = load_index()
    counter_ckpts = {c["checkpoint_id"] for c in ckpt.find({"snapshot_id": snapshot}, {"checkpoint_id": 1, "task_id": 1})
                     if c["task_id"] in index and is_counter_pattern(index[c["task_id"]])}
    same, margins, rows = 0, [], []
    fam_total, fam_same = defaultdict(int), defaultdict(int)
    for tid in dev:
        task = load_task(tid)
        q = load_query(task)
        own_doc = ckpt.find_one({"snapshot_id": snapshot, "task_id": tid}, {"_id": 1})
        stage = _vector_search(query_input(q), snapshot, config.PROTOCOL)
        stage["$vectorSearch"]["limit"] = max(stage["$vectorSearch"]["limit"], n_snapshot)
        stage["$vectorSearch"]["numCandidates"] = max(stage["$vectorSearch"]["numCandidates"], 10 * n_snapshot)
        exclude = [{"$match": {"_id": {"$ne": own_doc["_id"]}}}] if own_doc else []
        hits = list(ckpt.aggregate([stage, *exclude,
                                    {"$project": {"_id": 0, "checkpoint_id": 1, "family": 1,
                                                  "s": {"$meta": "vectorSearchScore"}}}]))
        top1_same = bool(hits) and hits[0]["family"] == task.family
        same += top1_same
        fam_total[task.family] += 1
        fam_same[task.family] += top1_same
        m = hits[0]["s"] - hits[1]["s"] if len(hits) > 1 else None
        margins.append(m)
        cp = is_counter_pattern(index[tid])
        rows.append({"task_id": tid, "family": task.family, "own_checkpoint": bool(own_doc),
                     "top1": hits[0]["checkpoint_id"] if hits else None, "top1_family": hits[0]["family"] if hits else None,
                     "top2": hits[1]["checkpoint_id"] if len(hits) > 1 else None, "top1_same_family": top1_same,
                     "margin": m, "counter_pattern_task": cp,
                     "top1_counter_pattern": (hits[0]["checkpoint_id"] in counter_ckpts) if hits else None})
        print(f"\n[{tid}] ({task.family}{', COUNTER PATTERN' if cp else ''}) query {q['query_sha256'][:12]}"
              f"{'' if own_doc else '  (no own checkpoint: nothing excluded)'}")
        for i, h in enumerate(hits[:2], 1):
            print(f"  top-{i}: {h['checkpoint_id']:<22} {h['family']:<20} semantic={h['s']:.4f}"
                  f"  {'SAME family' if h['family'] == task.family else 'OTHER family'}")
        print(f"  margin={m:+.4f}  all: " + ", ".join(f"{h['checkpoint_id']}={h['s']:.4f}" for h in hits))
    ms = sorted(x for x in margins if x is not None)
    print(f"\ntop-1 same family: {same}/{len(dev)}; margin min/median/max: "
          f"{ms[0]:+.4f} / {statistics.median(ms):+.4f} / {ms[-1]:+.4f}")
    for fam in sorted(fam_total):
        print(f"  {fam:<20} top-1 same family {fam_same[fam]}/{fam_total[fam]}")
    cps = [r for r in rows if r["counter_pattern_task"]]
    print(f"counter-pattern dev tasks: {len(cps)}; counter-pattern checkpoints in {snapshot}: {sorted(counter_ckpts)}")
    for r in cps:
        print(f"  {r['task_id']:<11} top-1 {r['top1']} ({r['top1_family']}) -> "
              f"{'counter pattern' if r['top1_counter_pattern'] else 'NOT a counter pattern'}")
    out = ROOT / "results" / "phase5" / f"loo-{snapshot}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "snapshot": snapshot, "checkpoints": n_snapshot, "top1_same_family": same, "tasks": len(dev),
        "per_family": {f: [fam_same[f], fam_total[f]] for f in sorted(fam_total)},
        "margin_min_median_max": [ms[0], statistics.median(ms), ms[-1]],
        "counter_pattern_checkpoints": sorted(counter_ckpts), "rows": rows}, indent=1) + "\n")


if __name__ == "__main__":
    main()
