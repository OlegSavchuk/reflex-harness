"""Run tasks x arms (smoke test on dev; Gate 8 on eval). One run per task per arm.

Usage: python scripts/run_suite.py --split dev --phase dev [--arms plain_retry fallback memory]
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reflex_harness.controller import ARMS, run_task, shared_first_attempt  # noqa: E402
from reflex_harness.runner import task_ids  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "runs"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=("dev", "eval"), required=True)
    ap.add_argument("--phase", choices=("dev", "eval"), required=True)
    ap.add_argument("--arms", nargs="+", choices=ARMS, default=list(ARMS))
    ap.add_argument("--tasks", nargs="*")
    ap.add_argument("--repeat", type=int, default=1, help="repeat index (seeds the random arm)")
    args = ap.parse_args()
    tasks = args.tasks or task_ids(args.split)
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    jobs = [(t, a) for t in tasks for a in args.arms]
    print(f"[suite] {args.phase}: {len(tasks)} tasks x {len(args.arms)} arms = {len(jobs)} runs", flush=True)
    # attempt 1 is generated once per task and replayed by every arm
    shared_ids = {t: f"{args.phase}-shared-{t}-{stamp}" for t in tasks}
    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        shared = dict(zip(tasks, pool.map(
            lambda t: shared_first_attempt(t, phase=args.phase, run_id=shared_ids[t]), tasks)))
    for t, a in shared.items():
        print(f"  shared attempt 1 [{t}]: edited={[e.split('::')[-1] for e in a.edited]} "
              f"failing={len(a.report.failed)} regressed={len(a.regressed)} solved={a.solved} "
              f"${a.cost_usd:.4f}", flush=True)

    def one(job):
        t, a = job
        lines = []
        try:
            doc = run_task(t, a, phase=args.phase, run_id=f"{args.phase}-{a}-{t}-{stamp}",
                           first_attempt=shared[t], shared_run_id=shared_ids[t], repeat=args.repeat,
                           log=lambda m: lines.append(m))
        except Exception as e:  # a failed run is reported, never retried silently
            doc = {"run_id": f"{args.phase}-{a}-{t}-{stamp}", "task_id": t, "arm": a,
                   "stop_reason": f"EXCEPTION {type(e).__name__}: {e}", "verified_fix": False,
                   "attempts": None, "configs_used": [], "cost_usd": 0.0}
        print(f"\n[{t} / {a}]\n" + "\n".join(lines) + f"\n  => {doc['stop_reason']}", flush=True)
        return doc

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        docs = list(pool.map(one, jobs))

    print(f"\n{'task':<12} {'arm':<12} {'stop_reason':<21} {'ok':<5} {'att':<3} {'switch@':<7} "
          f"{'chosen/designed':<22} {'top-1 (score)':<34} {'top-2 (score)':<34} {'pre-selection end':<36} cost")
    for d in docs:
        nb = d.get("neighbours") or []
        fmt = lambda x: (f"{x['family'][:3]}:{x['checkpoint_id'].split('-', 2)[-1]} "  # noqa: E731
                         f"({x.get('semantic_score') or 0:.3f})")
        if d.get("semantic_margin") is not None:
            d["pre_selection_end"] = (d.get("pre_selection_end") or "") + f" margin={d['semantic_margin']:+.3f}"
        cd = f"{d.get('chosen_config') or '-'}/{d.get('designed_config') or '-'}"
        print(f"{d['task_id']:<12} {d['arm']:<12} {str(d['stop_reason'])[:21]:<21} {str(d['verified_fix']):<5} "
              f"{str(d['attempts']):<3} {str(d.get('switch_attempt') or '-'):<7} {cd:<22} "
              f"{fmt(nb[0]) if nb else '-':<34} {fmt(nb[1]) if len(nb) > 1 else '-':<34} "
              f"{str(d.get('pre_selection_end') or '-'):<36} ${d['cost_usd']:.4f}")
    print()
    for a in args.arms:
        ds = [d for d in docs if d["arm"] == a]
        solved = sum(d["verified_fix"] for d in ds)
        cost = sum(d["cost_usd"] for d in ds)
        print(f"  {a:<12} verified {solved}/{len(ds)}  total ${cost:.4f}  "
              f"cost/verified fix {'$%.4f' % (cost / solved) if solved else 'n/a'}")
    OUT.mkdir(exist_ok=True)
    (OUT / f"suite-{args.phase}-{stamp}.json").write_text(json.dumps(docs, indent=1, default=str))


if __name__ == "__main__":
    main()
