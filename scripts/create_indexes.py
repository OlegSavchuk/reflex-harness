"""Create every index Reflex needs. Idempotent: existing indexes are left as they are.

Retrieval is semantic-only (Gate 9 P1): one Automated Embedding vector index. The Atlas Search
index `ckpt_text` used by Gate 8's lexical branch is no longer created or used.

Usage: python scripts/create_indexes.py [--wait]
  --wait   poll until both search indexes are queryable (up to 10 min)
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymongo.errors import OperationFailure  # noqa: E402
from pymongo.operations import SearchIndexModel  # noqa: E402

from reflex_harness import config  # noqa: E402
from reflex_harness.store import db  # noqa: E402

REGULAR = {
    "configs": [([("registry", 1), ("config_id", 1)], {"unique": True})],
    "checkpoints": [([("checkpoint_id", 1)], {"unique": True})],
    "attempts": [([("run_id", 1), ("attempt_n", 1)], {}),
                 ([("task_id", 1), ("phase", 1)], {})],
    "calls": [([("run_id", 1), ("component", 1)], {})],
}

SEARCH = {
    config.VECTOR_INDEX: ("vectorSearch", {"fields": [
        {"type": "autoEmbed", "modality": "text", "path": "failure_narrative",
         "model": config.EMBED_MODEL},
        {"type": "filter", "path": "snapshot_id"},
        {"type": "filter", "path": "compat.protocol"}]}),
}


def covers(have, want):
    """True if `have` contains everything in `want` (server adds defaults to definitions)."""
    if isinstance(want, dict):
        return isinstance(have, dict) and all(k in have and covers(have[k], v) for k, v in want.items())
    if isinstance(want, list):
        return isinstance(have, list) and all(any(covers(h, w) for h in have) for w in want)
    return have == want


def search_status(coll):
    return {i["name"]: i for i in coll.list_search_indexes()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", action="store_true")
    args = ap.parse_args()
    d = db()

    for name, specs in REGULAR.items():
        for keys, opts in specs:
            idx = d[name].create_index(keys, **opts)
            print(f"regular  {name}.{idx}{'  (unique)' if opts.get('unique') else ''}")

    ckpt = d["checkpoints"]
    if "checkpoints" not in d.list_collection_names():
        d.create_collection("checkpoints")
    existing = search_status(ckpt)
    failed = False
    for name, (kind, definition) in SEARCH.items():
        if name in existing:
            drift = not covers(existing[name].get("latestDefinition", {}), definition)
            print(f"search   checkpoints.{name} exists"
                  f"{'  WARNING: definition differs from script; drop it in Atlas to recreate' if drift else ''}")
            continue
        try:
            ckpt.create_search_index(SearchIndexModel(definition=definition, name=name, type=kind))
            print(f"search   checkpoints.{name} created ({kind})")
        except OperationFailure as e:
            failed = True
            print(f"search   checkpoints.{name} FAILED: {e.details.get('errmsg', str(e))[:300]}")
            if kind == "vectorSearch":
                print("         autoEmbed needs storage auto-scaling ON (Atlas > cluster > Edit > Storage).\n"
                      "         If the sandbox policy blocks it: ask MongoDB staff; fallback is SPEC §17.")
    if failed:
        sys.exit(1)

    deadline = time.time() + (600 if args.wait else 0)
    while True:
        status = search_status(ckpt)
        line = "  ".join(f"{n}={status[n].get('status')}/queryable={status[n].get('queryable')}"
                         for n in SEARCH if n in status)
        ready = all(status.get(n, {}).get("queryable") for n in SEARCH)
        bad = [n for n in SEARCH if status.get(n, {}).get("status") == "FAILED"]
        if ready or bad or time.time() >= deadline:
            print(f"status   {line}")
            break
        print(f"waiting  {line}")
        time.sleep(10)
    if bad:
        for n in bad:
            print(f"search   {n} FAILED: {status[n].get('message', '')[:300]}")
        sys.exit(1)
    if args.wait and not ready:
        sys.exit("search indexes not queryable after 10 min")
    print("OK" if ready else "created; not queryable yet (rerun with --wait)")


if __name__ == "__main__":
    main()
