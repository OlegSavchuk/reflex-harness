"""Leave-one-out retrieval on dev tasks (eval-free preview of neighbourhood quality).

For each dev task: its stored query (tasks/<id>/query.json) runs through the semantic
$vectorSearch stage with the task's own checkpoint excluded. Reports top-1/top-2 with
families, semantic scores and the margin, plus every other checkpoint's score.
The own checkpoint is excluded after the search stage (`_id` is not an indexed filter field);
exact as long as the search limit covers the whole snapshot.

Usage: python scripts/loo_retrieval.py [--snapshot mem-v1]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reflex_harness import config  # noqa: E402
from reflex_harness.pipelines import _vector_search  # noqa: E402
from reflex_harness.queries import load_query, query_input  # noqa: E402
from reflex_harness.runner import load_task, task_ids  # noqa: E402
from reflex_harness.store import db  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=config.SNAPSHOT_ID)
    snapshot = ap.parse_args().snapshot
    ckpt = db()["checkpoints"]
    n_snapshot = ckpt.count_documents({"snapshot_id": snapshot})
    dev = task_ids("dev")
    same, margins = 0, []
    for tid in dev:
        task = load_task(tid)
        q = load_query(task)
        own = ckpt.find_one({"snapshot_id": snapshot, "task_id": tid}, {"_id": 1})["_id"]
        stage = _vector_search(query_input(q), snapshot, config.PROTOCOL)
        stage["$vectorSearch"]["limit"] = max(stage["$vectorSearch"]["limit"], n_snapshot)
        stage["$vectorSearch"]["numCandidates"] = max(stage["$vectorSearch"]["numCandidates"], 10 * n_snapshot)
        hits = list(ckpt.aggregate([stage, {"$match": {"_id": {"$ne": own}}},
                                    {"$project": {"_id": 0, "checkpoint_id": 1, "family": 1,
                                                  "s": {"$meta": "vectorSearchScore"}}}]))
        top1_same = bool(hits) and hits[0]["family"] == task.family
        same += top1_same
        m = hits[0]["s"] - hits[1]["s"] if len(hits) > 1 else None
        margins.append(m)
        print(f"\n[{tid}] ({task.family}) query {q['query_sha256'][:12]}")
        for i, h in enumerate(hits[:2], 1):
            print(f"  top-{i}: {h['checkpoint_id']:<22} {h['family']:<20} semantic={h['s']:.4f}"
                  f"  {'SAME family' if h['family'] == task.family else 'OTHER family'}")
        print(f"  margin={m:+.4f}  all: " + ", ".join(f"{h['checkpoint_id']}={h['s']:.4f}" for h in hits))
    ms = sorted(x for x in margins if x is not None)
    print(f"\ntop-1 same family: {same}/{len(dev)}; margin min/median/max: "
          f"{ms[0]:+.4f} / {ms[len(ms) // 2]:+.4f} / {ms[-1]:+.4f}")


if __name__ == "__main__":
    main()
