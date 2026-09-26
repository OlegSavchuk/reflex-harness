"""Report on a built memory snapshot (read-only, no model calls): content hash, checkpoints per
family, every checkpoint's single-attempt trial outcomes, dev tasks without a checkpoint, build
cost and tokens (measured `calls` rows of the build), counter-pattern checkpoints (SPEC §13.6).

Usage: python scripts/memory_report.py --snapshot mem-v2 --stamp <build stamp> [--build-json runs/memory/...]
Writes results/phase5/<snapshot>.json.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reflex_harness.runner import task_ids  # noqa: E402
from reflex_harness.store import db  # noqa: E402
from reflex_harness.task_index import caller_rule, is_counter_pattern, load_index  # noqa: E402
from snapshot_hash import snapshot_hash  # noqa: E402


def tag(o):
    return "VERIFIED" if o["verified"] else "diag-only" if o["solved"] else "regression" if o["regression"] else "failed"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--stamp", required=True, help="build stamp (run ids build-<snapshot>-<task>-<stamp>)")
    ap.add_argument("--build-json", help="the build's runs/memory/*.json (for why a task has no checkpoint)")
    args = ap.parse_args()
    index = load_index()
    h, n = snapshot_hash(args.snapshot)
    ckpts = list(db()["checkpoints"].find({"snapshot_id": args.snapshot}, {"_id": 0}).sort("checkpoint_id", 1))
    errors = {}
    if args.build_json:
        errors = {r["task_id"]: r["error"] for r in json.loads(Path(args.build_json).read_text()) if "error" in r}
    missing = [t for t in task_ids("dev") if t not in {c["task_id"] for c in ckpts}]
    calls = list(db()["calls"].find({"run_id": {"$regex": f"^build-{args.snapshot}-.*-{args.stamp}"}}, {"_id": 0}))
    comp = defaultdict(lambda: [0, 0, 0, 0, 0.0])
    for c in calls:
        x = comp[c["component"]]
        x[0] += 1
        x[1] += c.get("input_tokens") or 0
        x[2] += c.get("output_tokens") or 0
        x[3] += c.get("reasoning_tokens") or 0
        x[4] += c.get("cost_usd") or 0.0
    unmeasured = [f"{c['run_id']} a{c['attempt_n']}" for c in calls
                  if c.get("estimated") or not c.get("input_tokens") or not c.get("output_tokens")]
    rows = []
    print(f"{args.snapshot}: content sha256 {h} ({n} checkpoints)")
    print(f"per family: {dict(sorted(Counter(c['family'] for c in ckpts).items()))}")
    print(f"\n{'checkpoint':<24}{'family':<21}{'designed':<11}{'callers':>7}  rule  counter  "
          f"{'focused':<11}{'caller':<11}{'dependency':<11}{'diagnostic':<11}root cause from")
    for c in ckpts:
        e = index[c["task_id"]]
        out = {o["config_id"]: tag(o) for o in c["outcomes"]}
        cp = is_counter_pattern(e)
        rows.append({"checkpoint_id": c["checkpoint_id"], "task_id": c["task_id"], "family": c["family"],
                     "designed_config": e["designed_config"], "n_callers": e["n_callers"],
                     "counter_pattern": cp, "outcomes": out, "root_cause_from": c["root_cause_from"],
                     "prior_attempts": len(c["prior_attempts"]), "narrative_violations": c["narrative_violations"],
                     "build_cost_usd": c["build_cost_usd"]})
        print(f"{c['checkpoint_id']:<24}{c['family']:<21}{e['designed_config']:<11}{e['n_callers']:>7}  "
              f"{caller_rule(e['n_callers'])[:4]:<6}{'YES' if cp else '-':<9}"
              + "".join(f"{out.get(k, 'missing'):<11}" for k in ("focused", "caller", "dependency", "diagnostic"))
              + f"{c['root_cause_from']}{'  NARRATIVE INVALID' if c['narrative_violations'] else ''}")
    for t in missing:
        print(f"NO CHECKPOINT {t}: {errors.get(t, 'see the build log')}")
    counter = [r["checkpoint_id"] for r in rows if r["counter_pattern"]]
    print(f"\ncounter-pattern dev checkpoints (SPEC §13.6): {len(counter)} -> {counter}")
    designed_verified = sum(r["outcomes"].get(r["designed_config"]) == "VERIFIED" for r in rows)
    print(f"designed config verified in its trial: {designed_verified}/{len(rows)}")
    tot = [sum(v[i] for v in comp.values()) for i in range(5)]
    print(f"build calls: {tot[0]} ({', '.join(f'{k} {v[0]}' for k, v in sorted(comp.items()))}); "
          f"{tot[1]:,} in / {tot[2]:,} out (reasoning {tot[3]:,}) = {tot[1] + tot[2]:,} tokens; ${tot[4]:.4f}; "
          f"calls without measured counts: {len(unmeasured)}")
    out = ROOT / "results" / "phase5" / f"{args.snapshot}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "snapshot": args.snapshot, "content_sha256": h, "checkpoints": n, "build_stamp": args.stamp,
        "per_family": dict(Counter(c["family"] for c in ckpts)), "rows": rows,
        "no_checkpoint": {t: errors.get(t) for t in missing}, "counter_pattern_checkpoints": counter,
        "designed_config_verified": designed_verified,
        "build": {"calls": tot[0], "input_tokens": tot[1], "output_tokens": tot[2], "reasoning_tokens": tot[3],
                  "cost_usd": round(tot[4], 6), "by_component": {k: v[:4] + [round(v[4], 6)] for k, v in comp.items()},
                  "unmeasured_calls": unmeasured}}, indent=1) + "\n")


if __name__ == "__main__":
    main()
