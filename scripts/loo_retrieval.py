"""Leave-one-out retrieval on dev tasks (eval-free preview of neighbourhood quality).

For each dev task: the eval-style query (narrator on seed code + seed failing tests, fix not
known; symbols from the seed baseline) runs through the frozen $rankFusion stage with the
task's own checkpoint excluded inside both branches. Reports top-1/top-2 with families,
fusion scores, per-branch ranks, and each branch's raw scores for every other checkpoint.

Usage: python scripts/loo_retrieval.py [--snapshot mem-v1]
"""
import argparse
import copy
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reflex_harness import config  # noqa: E402
from reflex_harness.context import pin_focal  # noqa: E402
from reflex_harness.narrator import forbidden_tokens, narrate_task, task_symbols  # noqa: E402
from reflex_harness.pipelines import NEIGHBORHOOD, _rank_fusion  # noqa: E402
from reflex_harness.runner import TASKS_DIR, LocalRunner, load_task  # noqa: E402
from reflex_harness.store import db  # noqa: E402


def loo_stage(narrative, symbols, snapshot, protocol, own_id):
    stage = copy.deepcopy(_rank_fusion(narrative, symbols, snapshot, protocol))
    pipes = stage["$rankFusion"]["input"]["pipelines"]
    # `_id` is not an indexed filter field in ckpt_vec, so exclude after each search stage.
    # Exact for LOO here: each branch's limit (4) covers the whole snapshot (4 checkpoints),
    # so nothing is lost and RRF ranks are computed on the remaining checkpoints.
    pipes["semantic"].insert(1, {"$match": {"_id": {"$ne": own_id}}})
    pipes["lexical"].insert(1, {"$match": {"_id": {"$ne": own_id}}})
    return stage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=config.SNAPSHOT_ID)
    snapshot = ap.parse_args().snapshot
    ckpt = db()["checkpoints"]
    runner = LocalRunner()
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    dev = sorted(p.name for p in TASKS_DIR.iterdir()
                 if (p / "task.json").is_file() and load_task(p.name).split == "dev")
    same_family_top1 = 0
    for tid in dev:
        task = load_task(tid)
        ws = runner.prepare(task)
        base = runner.run(ws, task.diag_cmd, 60)
        pinned = pin_focal(ws, base)
        runner.cleanup(ws)
        seed = {p: (task.repo / p).read_text() for p in task.allowlist}
        symbols = task_symbols(pinned.function, base)
        narrative, violations, _ = narrate_task(seed, base, pinned.function, None,
                                                forbidden_tokens(task.repo, task.allowlist, symbols),
                                                run_id=f"loo-{tid}-{stamp}", phase="dev", attempt_n=0)
        own = ckpt.find_one({"snapshot_id": snapshot, "task_id": tid}, {"_id": 1})["_id"]
        hood = list(ckpt.aggregate([loo_stage(narrative, symbols, snapshot, config.PROTOCOL, own),
                                    {"$limit": NEIGHBORHOOD},
                                    {"$project": {"_id": 0, "checkpoint_id": 1, "family": 1,
                                                  "fusion": {"$meta": "scoreDetails"}}}]))
        sem = list(ckpt.aggregate([{"$vectorSearch": {
            "index": config.VECTOR_INDEX, "path": "failure_narrative", "query": narrative,
            "numCandidates": 40, "limit": 4, "filter": {"snapshot_id": snapshot}}},
            {"$match": {"_id": {"$ne": own}}},
            {"$project": {"_id": 0, "checkpoint_id": 1, "family": 1, "s": {"$meta": "vectorSearchScore"}}}]))
        lex = list(ckpt.aggregate([{"$search": {"index": config.TEXT_INDEX, "compound": {
            "must": [{"text": {"query": symbols, "path": "error_symbols"}}],
            "filter": [{"equals": {"path": "snapshot_id", "value": snapshot}}]}}},
            {"$match": {"_id": {"$ne": own}}},
            {"$project": {"_id": 0, "checkpoint_id": 1, "family": 1, "s": {"$meta": "searchScore"}}}]))
        fam = task.family
        top1_same = bool(hood) and hood[0]["family"] == fam
        same_family_top1 += top1_same
        print(f"\n[{tid}] ({fam}) query narrative{' INVALID ' + str(violations) if violations else ''}:")
        print(f"  {narrative}")
        print(f"  symbols: {symbols}")
        for i, h in enumerate(hood, 1):
            ranks = {d["inputPipelineName"]: d.get("rank") for d in h["fusion"].get("details", [])}
            print(f"  top-{i}: {h['checkpoint_id']:<20} {h['family']:<20} fusion={h['fusion']['value']:.5f} "
                  f"semantic_rank={ranks.get('semantic', '-')} lexical_rank={ranks.get('lexical', '-')}"
                  f"  {'SAME family' if h['family'] == fam else 'OTHER family'}")
        print("  semantic (vectorSearchScore): " + ", ".join(f"{x['checkpoint_id'].replace('mem-v1-', '')}={x['s']:.4f}" for x in sem))
        print("  lexical  (searchScore):       " + (", ".join(f"{x['checkpoint_id'].replace('mem-v1-', '')}={x['s']:.3f}" for x in lex) or "no matches"))
    print(f"\ntop-1 same family: {same_family_top1}/{len(dev)}")


if __name__ == "__main__":
    main()
