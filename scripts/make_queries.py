"""Generate the fixed retrieval query for each task (tasks/<id>/query.json). One narrator call
per task; refuses to overwrite an existing query unless --force (queries are frozen artifacts).

Usage: python scripts/make_queries.py [task_id ...] [--force]
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reflex_harness.queries import QUERY_FILE, load_query, make_query  # noqa: E402
from reflex_harness.runner import TASKS_DIR, load_task  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks", nargs="*")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    ids = args.tasks or sorted(p.name for p in TASKS_DIR.iterdir() if (p / "task.json").is_file())
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    total, bad = 0.0, []
    for tid in ids:
        task = load_task(tid)
        path = task.root / QUERY_FILE
        if path.exists() and not args.force:
            print(f"{tid}: exists ({load_query(task)['query_sha256'][:12]}), skipped")
            continue
        q = make_query(task, run_id=f"make-query-{tid}-{stamp}")
        path.write_text(json.dumps(q, indent=1) + "\n")
        load_query(task)  # re-read and verify the hash
        total += q["cost_usd"]
        if q["narrative_violations"]:
            bad.append(tid)
        print(f"{tid}: {q['query_sha256'][:12]}  {q['narrative']}"
              f"{'  INVALID ' + str(q['narrative_violations']) if q['narrative_violations'] else ''}")
    print(f"\nnarrator cost ${total:.4f}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
