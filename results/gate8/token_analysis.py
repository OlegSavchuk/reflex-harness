"""Gate 8 token usage. SECONDARY, computed after the run, NOT pre-registered.

Read-only: the 60 Gate 8 run records in results/gate8/runs/*.json plus their `calls` and
`attempts` rows in MongoDB (reflex). No model calls, no writes. Writes results/gate8/tokens.txt.

Accounting (the same as Gate 8 cost): attempt 1 was generated once per task and repeat
(`eval-shared-*` run ids) and replayed in all three arms, so its tokens are counted in every arm,
just as its cost is in `runs.cost_usd`. The stored `runs.input_tokens` / `output_tokens` hold only
each run's own calls (attempt 1 excluded); both views are reported. Tokens are the provider's
counts from each call's `usage`; reasoning tokens are reported separately by the API and are
part of output tokens. Embedding rows carry harness *estimates* (Atlas embedded the query
server-side, usage not visible): they are listed, never added to totals.

Usage (repo root, venv): python results/gate8/token_analysis.py
"""
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from reflex_harness.store import db  # noqa: E402

HERE = Path(__file__).resolve().parent
FAMILY = {"oscillation": "A", "semantic_repetition": "B"}
ARMS = ("plain_retry", "fallback", "memory")
MEMV1_BUILD = r"^build-mem-v1-.*-20260926T163015"      # evidence of mem-v1 (content 84cbf2b1)
MEMV1_RENARRATE = r"^renarrate-.*20260926T170018"     # in-place re-narration before the freeze
OTHER_BUILDS = r"^build-mem-v1-.*-20260926T(161118|165505)"   # archived builds, not in mem-v1


def tok(calls):
    i = sum(c.get("input_tokens") or 0 for c in calls)
    o = sum(c.get("output_tokens") or 0 for c in calls)
    r = sum(c.get("reasoning_tokens") or 0 for c in calls)
    return i, o, r


def fmt(n):
    return f"{n:,.0f}" if isinstance(n, (int, float)) else n


def main():
    runs = [d for f in sorted(glob.glob(str(HERE / "runs" / "*.json"))) for d in json.loads(Path(f).read_text())]
    shared_ids = sorted({d["shared_attempt"]["run_id"] for d in runs if d.get("shared_attempt")})
    all_ids = [d["run_id"] for d in runs] + shared_ids
    calls = list(db()["calls"].find({"run_id": {"$in": all_ids}}, {"_id": 0}).sort([("run_id", 1), ("attempt_n", 1)]))
    measured = [c for c in calls if c["component"] in ("agent", "narrator")]
    estimated = [c for c in calls if c["component"] not in ("agent", "narrator")]
    by_run = defaultdict(list)
    for c in measured:
        by_run[c["run_id"]].append(c)
    L = []
    w = L.append
    w("GATE 8 TOKEN USAGE — SECONDARY, computed after the run, NOT pre-registered")
    w("Source: results/gate8/runs/*.json (60 runs) + MongoDB `calls`/`attempts` rows for those run ids. Read-only.")
    w("Frozen code 26b79a7, mem-v1 c701ea5e. Family A = oscillation, B = semantic_repetition.")
    w("Tokens = provider-reported usage per call. Reasoning tokens are reported separately by the API and are")
    w("INCLUDED in output tokens (not additional). Attempt 1 (shared) is counted in every arm, like its cost.")
    w("")

    # ---------- data completeness ----------
    missing = []
    for c in measured:
        if not c.get("input_tokens") or not c.get("output_tokens") or c.get("reasoning_tokens") is None:
            missing.append(f"{c['run_id']} attempt {c['attempt_n']} {c['component']}")
    over = [c for c in measured if (c.get("reasoning_tokens") or 0) > (c.get("output_tokens") or 0)]
    atts = list(db()["attempts"].find({"run_id": {"$in": [d["run_id"] for d in runs]}},
                                      {"_id": 0, "run_id": 1, "attempt_n": 1, "config_id": 1}))
    no_call = [f"{a['run_id']} attempt {a['attempt_n']}" for a in atts
               if a["attempt_n"] > 1 and not any(c["attempt_n"] == a["attempt_n"] and c["component"] == "agent"
                                                 for c in by_run[a["run_id"]])]
    no_shared = [s for s in shared_ids if not by_run[s]]
    w("DATA COMPLETENESS")
    w(f"  measured calls (agent + narrator): {len(measured)}; with missing input/output/reasoning counts: "
      f"{len(missing)}{' -> ' + '; '.join(missing) if missing else ''}")
    w(f"  calls with reasoning > output tokens: {len(over)}")
    w(f"  attempts >= 2 without an agent call row: {len(no_call)}{' -> ' + '; '.join(no_call) if no_call else ''}")
    w(f"  shared attempt-1 runs without a call row: {len(no_shared)}{' -> ' + '; '.join(no_shared) if no_shared else ''}")
    est_runs = sorted({c["run_id"] for c in estimated})
    w(f"  NOT MEASURED: {len(estimated)} `embed` rows ({sorted({c['component'] for c in estimated})}) in "
      f"{len(est_runs)} memory runs carry harness estimates (Atlas embedded the query server-side);")
    w("  excluded from every total below. Runs: " + ", ".join(est_runs))
    w("")

    # ---------- per arm x family ----------
    cells = defaultdict(lambda: {"runs": 0, "fixed": 0, "attempts": 0, "calls": [], "nofix": [], "own": [0, 0]})
    for d in runs:
        cs = by_run[d["run_id"]] + (by_run[d["shared_attempt"]["run_id"]] if d.get("shared_attempt") else [])
        for key in ((d["arm"], FAMILY[d["family"]]), (d["arm"], "all")):
            cell = cells[key]
            cell["runs"] += 1
            cell["fixed"] += bool(d["verified_fix"])
            cell["attempts"] += d["attempts"] or 0
            cell["calls"] += cs
            if not d["verified_fix"]:
                cell["nofix"] += cs
            cell["own"][0] += d.get("input_tokens") or 0
            cell["own"][1] += d.get("output_tokens") or 0
    head = (f"{'arm':<12}{'fam':<4}{'runs':>5}{'fixed':>6}{'input':>9}{'output':>9}{'reasoning':>10}{'total':>10}"
            f"{'per run':>9}{'per att':>9}{'per fix':>10}{'no-fix runs':>18}")
    w("PER ARM AND FAMILY (all measured tokens, attempt 1 included; 'total' = input + output)")
    w(head)
    w("-" * len(head))
    for arm in ARMS:
        for fam in ("A", "B", "all"):
            c = cells[(arm, fam)]
            i, o, r = tok(c["calls"])
            t = i + o
            ni, no, _ = tok(c["nofix"])
            per_fix = fmt(t / c["fixed"]) if c["fixed"] else "n/a (0)"
            w(f"{arm:<12}{fam:<4}{c['runs']:>5}{c['fixed']:>6}{fmt(i):>9}{fmt(o):>9}{fmt(r):>10}{fmt(t):>10}"
              f"{fmt(t / c['runs']):>9}{fmt(t / c['attempts']):>9}{per_fix:>10}"
              f"{fmt(ni + no):>9} ({(ni + no) / t:.0%})")
        w("")
    w("  per att = total / attempts made (attempt 1 counted in each arm); per fix = all tokens of the cell,")
    w("  failed runs included, / verified fixes; no-fix runs = tokens spent in runs that ended without a verified fix.")
    w("")

    # ---------- components ----------
    w("BY COMPONENT (memory arm only uses the narrator: one query narrative per switch)")
    for arm in ARMS:
        comp = defaultdict(list)
        for c in cells[(arm, "all")]["calls"]:
            comp[c["component"]].append(c)
        w("  " + f"{arm:<12}" + "  ".join(f"{k}: {len(v)} calls, {fmt(sum(tok(v)[:2]))} tokens" for k, v in sorted(comp.items())))
    w("")

    # ---------- stored run fields vs this accounting ----------
    w("STORED runs.input_tokens/output_tokens (own calls only, attempt 1 excluded) vs this accounting")
    for arm in ARMS:
        c = cells[(arm, "all")]
        i, o, _ = tok(c["calls"])
        w(f"  {arm:<12} stored {fmt(c['own'][0])} in / {fmt(c['own'][1])} out; with attempt 1: {fmt(i)} in / {fmt(o)} out")
    est_in = sum(c.get("input_tokens") or 0 for c in estimated)
    w(f"  The stored memory totals also include the {len(estimated)} estimated embed rows ({fmt(est_in)} input tokens),")
    w("  which this accounting excludes. runs.cost_usd includes attempt 1 but the stored token fields do not")
    w("  (same code in Gate 9).")
    w("")

    # ---------- mean input tokens per attempt by config ----------
    cfg_of = {(a["run_id"], a["attempt_n"]): a["config_id"] for a in atts}
    per_attempt = defaultdict(lambda: [0, 0])
    for c in measured:
        if c["component"] != "agent":
            continue
        cfg = "focused" if c["run_id"] in shared_ids else cfg_of.get((c["run_id"], c["attempt_n"]))
        k = (cfg, c["run_id"], c["attempt_n"])
        per_attempt[k][0] += c.get("input_tokens") or 0
        per_attempt[k][1] += c.get("output_tokens") or 0
    by_cfg = defaultdict(list)
    for (cfg, _, _), (i, o) in per_attempt.items():
        by_cfg[cfg].append((i, o))
    w("MEAN TOKENS PER ATTEMPT BY CONTEXT CONFIG (each generated attempt once; shared attempt 1 counted once)")
    w(f"  {'config':<12}{'attempts':>9}{'mean input':>12}{'mean output':>13}")
    for cfg in ("focused", "caller", "dependency", "diagnostic", None):
        if cfg in by_cfg:
            v = by_cfg[cfg]
            w(f"  {str(cfg):<12}{len(v):>9}{fmt(sum(x for x, _ in v) / len(v)):>12}{fmt(sum(y for _, y in v) / len(v)):>13}")
    w("")

    # ---------- mem-v1 setup ----------
    w("MEM-V1 BUILD (one-off setup cost, not per run)")
    for label, rx in (("build 20260926T163015 (mem-v1 evidence: 4 dev tasks x 4 config trials + narrator)", MEMV1_BUILD),
                      ("re-narration 20260926T170018 (narrator only, before the freeze)", MEMV1_RENARRATE),
                      ("archived builds 161118 + 165505 (not in mem-v1; dev spend)", OTHER_BUILDS)):
        cs = list(db()["calls"].find({"run_id": {"$regex": rx}}, {"_id": 0}))
        i, o, r = tok(cs)
        miss = sum(1 for c in cs if not c.get("input_tokens") or not c.get("output_tokens"))
        kinds = defaultdict(int)
        for c in cs:
            kinds[c["component"]] += 1
        w(f"  {label}")
        w(f"    {len(cs)} calls ({', '.join(f'{k} {n}' for k, n in sorted(kinds.items()))}); "
          f"{fmt(i)} in / {fmt(o)} out (reasoning {fmt(r)}) = {fmt(i + o)} tokens; "
          f"${sum(c.get('cost_usd') or 0 for c in cs):.4f}; missing counts: {miss}")
    (HERE / "tokens.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
