"""Gate 8 lexical-branch evidence (Gate 9 P1 "token analysis"), reproducible and read-only.

Gate 8 fused `$vectorSearch` with a lexical `$search` on `error_symbols` (index `ckpt_text`,
lucene.whitespace: case-sensitive exact tokens). This script shows why that branch was inert and
could be removed (commit c34392d):
  1. each Gate 8 task's symbol set after the exception stoplist (stored query `error_symbols`,
     the same `task_symbols()` Gate 8 used), and every token shared by any two tasks;
  2. each Gate 8 eval query's lexical matches against mem-v1: offline token overlap, and the real
     `$search` count while the Gate 8 index `ckpt_text` still exists (never created by code now);
  3. for every logged Gate 8 memory decision, the overlap of its logged `error_symbols` with
     mem-v1: zero overlap means the lexical branch returned nothing, so `$rankFusion` ordered by
     the semantic branch alone and could not change top-1 or top-2.
Also reports the token overlap across all current active tasks (informational). No writes to
Atlas, no model calls. Output: results/phase1/lexical_evidence.json.
"""
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reflex_harness import config  # noqa: E402
from reflex_harness.queries import load_query  # noqa: E402
from reflex_harness.runner import load_task, task_ids  # noqa: E402
from reflex_harness.store import db  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GATE8_TASKS = ["osc-dev-01", "osc-dev-02", "osc-eval-01", "osc-eval-02",
               "sem-dev-01", "sem-dev-02", "sem-eval-01", "sem-eval-02"]
GATE8_RUNS = r"^eval-memory-.*-20260926T(173508|173715|173901|174056|174311)$"   # results/gate8/runs
GATE8_TEXT_INDEX = "ckpt_text"


def symbols(task_id: str) -> set[str]:
    return set(load_query(load_task(task_id))["error_symbols"].split())


def shared_pairs(ids: list[str]) -> list[dict]:
    sets = {t: symbols(t) for t in ids}
    return [{"pair": [a, b], "shared": sorted(sets[a] & sets[b])}
            for a, b in itertools.combinations(ids, 2) if sets[a] & sets[b]]


def search_count(ck, text: str) -> int | None:
    if GATE8_TEXT_INDEX not in {i["name"] for i in ck.list_search_indexes()}:
        return None
    return next(ck.aggregate([
        {"$search": {"index": GATE8_TEXT_INDEX, "compound": {
            "must": [{"text": {"query": text, "path": "error_symbols"}}],
            "filter": [{"equals": {"path": "snapshot_id", "value": config.SNAPSHOT_ID}},
                       {"equals": {"path": "compat.protocol", "value": config.PROTOCOL}}]}}},
        {"$count": "n"}]), {"n": 0})["n"]


def main():
    ck = db()["checkpoints"]
    memory = {c["checkpoint_id"]: set(c["error_symbols"].split())
              for c in ck.find({"snapshot_id": config.SNAPSHOT_ID}, {"checkpoint_id": 1, "error_symbols": 1})}
    out = {"snapshot": config.SNAPSHOT_ID,
           "gate8_symbols": {t: sorted(symbols(t)) for t in GATE8_TASKS},
           "gate8_shared_pairs": shared_pairs(GATE8_TASKS),
           "gate8_pairs": len(GATE8_TASKS) * (len(GATE8_TASKS) - 1) // 2}
    evals = []
    for t in GATE8_TASKS:
        if load_task(t).split != "eval":
            continue
        q = symbols(t)
        evals.append({"task_id": t, "offline_matches": {c: sorted(q & s) for c, s in memory.items() if q & s},
                      "search_count": search_count(ck, " ".join(sorted(q)))})
    out["gate8_eval_queries"] = evals
    decisions = []
    for d in db()["decisions"].find({"run_id": {"$regex": GATE8_RUNS}, "error_symbols": {"$exists": True}},
                                    {"run_id": 1, "task_id": 1, "error_symbols": 1}).sort("run_id", 1):
        s = set(d["error_symbols"].split())
        decisions.append({"run_id": d["run_id"], "overlap": {c: sorted(s & m) for c, m in memory.items() if s & m}})
    out["gate8_memory_decisions"] = decisions
    active = task_ids()
    out["active_tasks"] = len(active)
    out["active_shared_pairs"] = shared_pairs(active)

    print(f"Gate 8 tasks ({len(GATE8_TASKS)}), symbols after the stoplist:")
    for t, s in out["gate8_symbols"].items():
        print(f"  {t:<12} {' '.join(s)}")
    print(f"shared tokens across {out['gate8_pairs']} Gate 8 task pairs: {out['gate8_shared_pairs'] or 'none'}")
    for e in evals:
        print(f"  eval query {e['task_id']:<12} offline matches vs {config.SNAPSHOT_ID}: {e['offline_matches'] or 0}"
              f"   $search count: {e['search_count'] if e['search_count'] is not None else 'index gone'}")
    hit = [d for d in decisions if d["overlap"]]
    print(f"Gate 8 memory decisions: {len(decisions)}; with any lexical overlap: {len(hit)}"
          f" -> lexical branch {'could have' if hit else 'could not have'} changed top-1/top-2")
    print(f"current active tasks: {len(active)}; pairs sharing a token: {len(out['active_shared_pairs'])}")
    for p in out["active_shared_pairs"]:
        print(f"  {p['pair'][0]} / {p['pair'][1]}: {p['shared']}")
    path = ROOT / "results" / "phase1" / "lexical_evidence.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
