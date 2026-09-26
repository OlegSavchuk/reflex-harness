"""Phase 3 detection report (SPEC §13.7): first-trigger distribution over the pre-declared dev
runs, with every attempt's outcome. Read-only (runs/ suite files + `attempts`); no model calls.

Usage: python scripts/detection_report.py runs/suite-dev-A.json runs/suite-dev-B.json ...
Writes results/phase3/detection.json.
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reflex_harness.store import db  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = [Path(p) for p in sys.argv[1:]]
    runs = [d for f in files for d in json.loads(f.read_text())]
    rows = []
    for d in sorted(runs, key=lambda d: (d["task_id"], d.get("repeat") or 0)):
        atts = [{"attempt_n": a["attempt_n"], "config": a["config_id"], "failing": len(a["failed_tests"]),
                 "regression": a["regression"], "diag_pass": a["diag_pass"], "verified": a.get("verified"),
                 "rolled_back": a["rolled_back"], "trigger": a.get("trigger")}
                for a in db()["attempts"].find({"run_id": d["run_id"]}).sort("attempt_n", 1)]
        first = d["triggers"][0] if d.get("triggers") else None
        rows.append({"task_id": d["task_id"], "repeat": d.get("repeat"), "run_id": d["run_id"],
                     "first_trigger": first["trigger"] if first else None,
                     "first_trigger_attempt": first["attempt_n"] if first else None,
                     "stop_reason": d["stop_reason"], "switch_attempt": d.get("switch_attempt"),
                     "cost_usd": d["cost_usd"], "attempts": atts})
    dist = Counter(r["first_trigger"] or f"none ({r['stop_reason']})" for r in rows)
    same = dist.get("same_strategy", 0)
    verdict = "PASS" if same * 2 > len(rows) else "FAIL"
    print(f"{'task':<11} {'rep':<4} {'first trigger':<14} {'@':<2} {'stop':<30} attempts (config: failing, reg, diag, verified)")
    for r in rows:
        at = "; ".join(f"{a['attempt_n']}{a['config'][0]}: {a['failing']}f{' R' if a['regression'] else ''}"
                       f"{' diag' if a['diag_pass'] else ''}{' V' if a['verified'] else ''}" for a in r["attempts"])
        print(f"{r['task_id']:<11} {str(r['repeat']):<4} {str(r['first_trigger']):<14} "
              f"{str(r['first_trigger_attempt'] or '-'):<2} {r['stop_reason']:<30} {at}")
    print(f"\nfirst-trigger distribution over {len(rows)} runs: {dict(dist)}")
    print(f"pre-declared pass (same_strategy first in more than half): {verdict} ({same}/{len(rows)})")
    out = ROOT / "results" / "phase3" / "detection.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"suite_files": [f.name for f in files], "distribution": dict(dist),
                               "same_strategy_first": same, "runs": len(rows), "verdict": verdict,
                               "cost_usd": round(sum(r["cost_usd"] for r in rows), 6), "rows": rows},
                              indent=1, default=str) + "\n")


if __name__ == "__main__":
    main()
