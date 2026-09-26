"""Gate 1: Atlas retrieval + selection, end to end, on throwaway fixtures.

Inserts 6 labelled fixture checkpoints under a separate snapshot id, waits until both
vector index sees them, runs paraphrased queries through the semantic $vectorSearch stage, checks the
selection pipeline (full sorted candidate table) against a Python reference of the same
scoring rule, checks a diagnostics-only solve does not count, flips one outcome and checks
the choice changes, then deletes the fixtures.
Fixtures are plumbing, never results.

Usage: python scripts/gate1_retrieval.py [--keep]
  --keep   leave fixtures in place for inspection (rerun without it to clean up)
"""
import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymongo.errors import OperationFailure  # noqa: E402

from reflex_harness import config  # noqa: E402
from reflex_harness.pipelines import retrieval_pipeline, selection_pipeline  # noqa: E402
from reflex_harness.store import db  # noqa: E402

FX_SNAPSHOT = "gate1-fixtures"
CONFIG_IDS = ["focused", "caller", "dependency", "diagnostic"]


def o(config_id, solved, regression, cost, verified=None):
    return {"config_id": config_id, "solved": solved,
            "verified": solved if verified is None else verified,
            "regression": regression, "cost_usd": cost}


FIXTURES = [
    ("fx-osc-1", "oscillation",
     "Fixing the shared total calculation for the invoice caller broke the refund caller, which "
     "passes amounts in a different unit. The agent then reverted the change to satisfy the refund "
     "test, and the invoice test failed again.",
     "calculate_total test_invoice_cents test_refund_dollars AssertionError",
     [o("focused", False, True, 0.021), o("caller", True, False, 0.034),
      o("dependency", True, False, 0.041), o("diagnostic", False, False, 0.052)]),
    ("fx-osc-2", "oscillation",
     "Adjusting the shared date parser to accept the format one importer sends made the other "
     "importer's timestamps shift by a day. Restoring the original parsing brought back the first "
     "importer's failure.",
     "parse_timestamp test_csv_import test_api_import ValueError AssertionError",
     [o("focused", False, True, 0.018), o("caller", True, False, 0.030),
      o("dependency", False, False, 0.036), o("diagnostic", False, False, 0.047)]),
    ("fx-osc-3", "oscillation",
     "A change to the common discount helper satisfied the checkout path but made loyalty pricing "
     "apply the discount twice. The agent alternated between the two behaviors across attempts.",
     "apply_discount test_checkout_total test_loyalty_price AssertionError",
     [o("focused", False, True, 0.019), o("caller", True, False, 0.029),
      o("dependency", False, False, 0.038), o("diagnostic", True, False, 0.060)]),
    ("fx-sem-1", "semantic_repetition",
     "The agent kept adjusting rounding and the order of arithmetic inside the report function, but "
     "every attempt left the same tests failing. The real defect was in the currency conversion "
     "helper it depends on, which the agent never examined.",
     "monthly_report convert_currency test_report_totals AssertionError",
     [o("focused", False, False, 0.020), o("caller", False, False, 0.031),
      o("dependency", True, False, 0.035), o("diagnostic", True, False, 0.050, verified=False)]),
    ("fx-sem-2", "semantic_repetition",
     "Successive attempts cast values to different numeric types in the averaging function without "
     "changing the result. The underlying issue was a data class whose default list was shared "
     "between instances.",
     "average_score ScoreBook test_average_isolated TypeError AssertionError",
     [o("focused", False, False, 0.017), o("caller", False, False, 0.027),
      o("dependency", True, False, 0.033), o("diagnostic", False, False, 0.049)]),
    ("fx-sem-3", "semantic_repetition",
     "Each patch rewrote the loop in the scheduling function a slightly different way while the same "
     "two tests kept failing. The helper that computes business days returned an off-by-one boundary, "
     "and it was outside the context the agent was given.",
     "next_slot business_days_between test_next_slot_weekend AssertionError",
     [o("focused", False, False, 0.022), o("caller", False, True, 0.030),
      o("dependency", True, False, 0.037), o("diagnostic", False, False, 0.051)]),
]

# Paraphrases: same failure pattern, different wording; symbols overlap only partially.
QUERIES = [
    ("oscillation", "fx-osc-1",
     "When the agent corrected the shared summing routine so the billing path passed, the "
     "reimbursement path started failing because it supplies values in another unit. Undoing the "
     "edit fixed reimbursements and broke billing again.",
     "calculate_total test_invoice_cents AssertionError"),
    ("semantic_repetition", "fx-sem-1",
     "Several patches tweaked rounding precision and reordered operations in the reporting code, yet "
     "the failing tests never changed. The fault sat in an exchange-rate helper the reporting code "
     "calls, which had not been looked at.",
     "monthly_report test_report_totals AssertionError"),
]

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{'  — ' + detail if detail else ''}")
    return ok


def fixture_docs():
    now = datetime.now(timezone.utc)
    return [{"checkpoint_id": cid, "snapshot_id": FX_SNAPSHOT, "family": fam,
             "task_id": f"fixture-{cid}", "failure_narrative": narr, "error_symbols": syms,
             "facets": {"callers_of_focal": 2 if fam == "oscillation" else 1, "files_touched": 1},
             "compat": {"language": "python", "protocol": config.PROTOCOL,
                        "registry": config.REGISTRY},
             "prior_attempts": [], "outcomes": outs, "created_at": now}
            for cid, fam, narr, syms, outs in FIXTURES]


def reference_choice(neighborhood, registry_configs, tried):
    """Python restatement of the frozen selection rule, used only to cross-check the pipeline.
    Sort: score desc, nearest solving neighbour's rank asc, mean_cost asc, order asc."""
    stats = {}
    for rank, ck in enumerate(neighborhood, 1):
        for out in ck["outcomes"]:
            if out["config_id"] in tried:
                continue
            s = stats.setdefault(out["config_id"], {"support": 0, "solves": 0, "regressions": 0,
                                                    "costs": [], "nsr": 99})
            s["support"] += 1
            solved = out["solved"] and out.get("verified", False)
            s["solves"] += solved
            s["regressions"] += out["regression"]
            s["costs"].append(out["cost_usd"])
            if solved:
                s["nsr"] = min(s["nsr"], rank)
    order = {c["config_id"]: c["order"] for c in registry_configs}
    for cid in order:
        if cid not in tried:
            stats.setdefault(cid, {"support": 0, "solves": 0, "regressions": 0, "costs": [], "nsr": 99})
    rows = [(cid, (s["solves"] - 2 * s["regressions"]) / (s["support"] + 1),
             sum(s["costs"]) / len(s["costs"]) if s["costs"] else 1e9, order.get(cid, 99), s["nsr"])
            for cid, s in stats.items()]
    rows.sort(key=lambda r: (-r[1], r[4], r[2], r[3]))
    return rows


def wait_searchable(ckpt, n, timeout_s=300):
    vec = [{"$vectorSearch": {"index": config.VECTOR_INDEX, "path": "failure_narrative",
                              "query": "agent failure", "numCandidates": 100, "limit": 20,
                              "filter": {"snapshot_id": FX_SNAPSHOT}}}, {"$count": "n"}]
    t0 = time.time()
    while True:
        nv = next(ckpt.aggregate(vec), {"n": 0})["n"]
        if nv == n or time.time() - t0 > timeout_s:
            return nv, time.time() - t0
        print(f"  ...  searchable: vector {nv}/{n} ({time.time() - t0:.0f}s)")
        time.sleep(5)


def probe_query_form(ckpt):
    """Which autoEmbed query form does this cluster accept? SPEC assumes a plain string."""
    forms = {"string": "shared function broke another caller",
             "object": {"text": "shared function broke another caller"}}
    out = {}
    for label, q in forms.items():
        try:
            list(ckpt.aggregate([{"$vectorSearch": {
                "index": config.VECTOR_INDEX, "path": "failure_narrative", "query": q,
                "numCandidates": 10, "limit": 1, "filter": {"snapshot_id": FX_SNAPSHOT}}}]))
            out[label] = "ok"
        except OperationFailure as e:
            out[label] = e.details.get("errmsg", str(e))[:160]
    return out


def show(neighborhood):
    for i, ck in enumerate(neighborhood, 1):
        print(f"        #{i} {ck['checkpoint_id']:<9} {ck['family']:<20} "
              f"semantic_score={ck['semantic_score']:.4f}")


def run_query(ckpt, family, target, narrative, symbols, registry_configs):
    print(f"\n[query] {family} paraphrase (target {target})")
    hood = list(ckpt.aggregate(retrieval_pipeline(narrative, FX_SNAPSHOT, config.PROTOCOL)))
    show(hood)
    check("neighborhood has 2 checkpoints", len(hood) == 2, f"got {len(hood)}")
    if not hood:
        return None, None
    check("top-1 is the paraphrased checkpoint", hood[0]["checkpoint_id"] == target,
          f"got {hood[0]['checkpoint_id']}")
    if any(h["family"] != family for h in hood):
        print(f"  WARN  neighborhood mixes families: {[h['family'] for h in hood]}")

    tried = ["focused"]
    rows = select(ckpt, narrative, symbols, tried)
    ref = reference_choice(hood, registry_configs, tried)
    for r in rows:
        print(f"        candidate {r['_id']:<11} score={r['score']:+.3f} support={r['support']} "
              f"solves={r['solves']} regressions={r['regressions']} nearest_solve_rank={r['nearest_solve_rank']} "
              f"mean_cost={r['mean_cost']:g} "
              f"evidence={r.get('evidence')}")
    check("all untried configs returned, sorted", [r["_id"] for r in rows] == [x[0] for x in ref]
          and len(rows) == 4 - len(tried), f"reference order {[x[0] for x in ref]}")
    check("scores == Python reference", len(rows) == len(ref) and all(
        abs(r["score"] - x[1]) < 1e-9 for r, x in zip(rows, ref)))
    raw_diag = sum(out["solved"] for ck in hood for out in ck["outcomes"]
                   if out["config_id"] == "diagnostic")
    unverified = sum(out["solved"] and not out["verified"] for ck in hood
                     for out in ck["outcomes"] if out["config_id"] == "diagnostic")
    if unverified:
        diag = next(r for r in rows if r["_id"] == "diagnostic")
        check("diagnostics-only solve not counted", diag["solves"] == raw_diag - unverified,
              f"diagnostic: solved={raw_diag}, verified solves counted={diag['solves']}")
    return hood, (rows[0] if rows else None)


def select(ckpt, narrative, symbols, tried):
    return list(ckpt.aggregate(selection_pipeline(narrative, FX_SNAPSHOT, config.PROTOCOL,
                                                  config.REGISTRY, tried)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()
    d = db()
    ckpt = d["checkpoints"]

    print("[preflight]")
    registry_configs = list(d["configs"].find({"registry": config.REGISTRY}, {"_id": 0}))
    if not check(f"4 configs in registry {config.REGISTRY}", len(registry_configs) == 4,
                 f"found {len(registry_configs)}; run scripts/seed_configs.py"):
        sys.exit(1)
    idx = {i["name"]: i for i in ckpt.list_search_indexes()}
    for name in (config.VECTOR_INDEX,):
        if not check(f"{name} queryable", bool(idx.get(name, {}).get("queryable")),
                     f"status={idx.get(name, {}).get('status', 'missing')}"):
            sys.exit("run: python scripts/create_indexes.py --wait")

    stale = ckpt.delete_many({"snapshot_id": FX_SNAPSHOT}).deleted_count
    if stale:
        print(f"  note  removed {stale} leftover fixtures from a previous run")

    try:
        print("\n[fixtures]")
        ckpt.insert_many(fixture_docs())
        print(f"  inserted {len(FIXTURES)} fixtures under snapshot_id={FX_SNAPSHOT!r}")
        nv, secs = wait_searchable(ckpt, len(FIXTURES))
        check("all fixtures searchable (autoEmbed)", nv == len(FIXTURES), f"vector {nv}, after {secs:.0f}s")

        forms = probe_query_form(ckpt)
        print(f"        autoEmbed query forms: {forms}")
        check("autoEmbed accepts query as plain string (SPEC form)", forms["string"] == "ok")

        (fam, target, narr, syms), sem_query = QUERIES
        hood, chosen = run_query(ckpt, fam, target, narr, syms, registry_configs)
        run_query(ckpt, *sem_query, registry_configs)
        if hood and chosen:
            print(f"\n[flip] {hood[0]['checkpoint_id']}: {chosen['_id']} -> solved=false, regression=true")
            ckpt.update_one({"checkpoint_id": hood[0]["checkpoint_id"]},
                            {"$set": {"outcomes.$[x].solved": False, "outcomes.$[x].regression": True}},
                            array_filters=[{"x.config_id": chosen["_id"]}])
            hood2 = list(ckpt.aggregate(retrieval_pipeline(narr, FX_SNAPSHOT, config.PROTOCOL)))
            check("same neighborhood after flip",
                  [h["checkpoint_id"] for h in hood2] == [h["checkpoint_id"] for h in hood])
            after = next(iter(select(ckpt, narr, syms, ["focused"])), None)
            ref = reference_choice(hood2, registry_configs, ["focused"])
            check("choice changed after flip", after is not None and after["_id"] != chosen["_id"],
                  f"{chosen['_id']} -> {after['_id'] if after else None} (score {after['score']:+.3f})"
                  if after else "empty")
            check("new choice == Python reference", after is not None and after["_id"] == ref[0][0],
                  f"reference {ref[0][0]}")

        if hood:
            print("\n[tie-break] caller solves only at rank 1 (expensive); dependency only at rank 2 (cheap)")
            r1, r2 = hood[0]["checkpoint_id"], hood[1]["checkpoint_id"]
            for cid, solver in ((r1, "caller"), (r2, "dependency")):
                ckpt.update_one({"checkpoint_id": cid}, {"$set": {"outcomes": [
                    o("focused", False, False, 0.02), o("caller", solver == "caller", False, 0.09),
                    o("dependency", solver == "dependency", False, 0.01), o("diagnostic", False, False, 0.05)]}})
            tied = select(ckpt, narr, syms, ["focused"])
            hood3 = list(ckpt.aggregate(retrieval_pipeline(narr, FX_SNAPSHOT, config.PROTOCOL)))
            ref = reference_choice(hood3, registry_configs, ["focused"])
            check("scores tie between caller and dependency",
                  len(tied) >= 2 and tied[0]["score"] == tied[1]["score"],
                  ", ".join(f"{r['_id']}={r['score']:+.3f}/r{r['nearest_solve_rank']}/${r['mean_cost']:g}" for r in tied))
            check("nearest neighbour's config wins the tie (not the cheapest)",
                  tied and tied[0]["_id"] == "caller" and tied[0]["mean_cost"] > tied[1]["mean_cost"])
            check("tie-break == Python reference", [r["_id"] for r in tied] == [x[0] for x in ref])

        print("\n[exhaustion]")
        none_left = select(ckpt, narr, syms, CONFIG_IDS)
        check("all configs tried -> empty result (configurations_exhausted)", not none_left,
              f"got {[r['_id'] for r in none_left]}" if none_left else "")
    finally:
        if args.keep:
            print(f"\n[cleanup] skipped (--keep); fixtures remain under {FX_SNAPSHOT!r}")
        else:
            n = ckpt.delete_many({"snapshot_id": FX_SNAPSHOT}).deleted_count
            left = ckpt.count_documents({"snapshot_id": FX_SNAPSHOT})
            print(f"\n[cleanup] deleted {n} fixtures")
            check("fixtures removed", left == 0, f"{left} remain")

    passed = sum(results)
    print(f"\nGate 1: {'PASS' if all(results) else 'FAIL'} ({passed}/{len(results)} checks)")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
