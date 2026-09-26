"""Gate 5: Jev smoke test on 10 dev cases; choose phrasing and THETA by separation.

Repeat cases pair two real calibration attempts under the same config (independent runs
used as attempts 1 and 2). Refinement cases are hand-built two-step patches on dev tasks.
Every failing set in every packet is measured by running the tests. No eval tasks.
Each case x phrasing is asked twice to expose sampling noise.

Usage: python scripts/jev_smoke.py [--samples 2]
"""
import argparse
import glob
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reflex_harness import jev  # noqa: E402
from reflex_harness.config import CONFIGS_R1  # noqa: E402
from reflex_harness.context import build_context, pin_focal  # noqa: E402
from reflex_harness.runner import LocalRunner, load_task  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CFG = {c["config_id"]: c for c in CONFIGS_R1}


def calib(task_id, config_id, i):
    f = sorted(glob.glob(str(ROOT / f"runs/calibration/{task_id}/calib-{task_id}-{config_id}-{i}-*.json")))[-1]
    return {x["path"]: x["content"] for x in json.load(open(f))["patch"]["files"]}


def edit(path, old, new):
    def f(files):
        assert files[path].count(old) == 1, (path, old)
        return {path: files[path].replace(old, new)}
    return f


REFUND_SEED = ("    gross = sum(item.quantity * item.unit_price for item in items)\n"
               "    return round(apply_tax(gross, tax_rate) - restocking_fee, 2)")
CAST_HACK = edit("billing/refund.py", REFUND_SEED,
                 "    gross = int(sum(item.quantity * item.unit_price for item in items))\n"
                 "    return round(apply_tax(gross, tax_rate) - restocking_fee, 2)")
JOB_SEED = "    return deadline_after(started_ms, job.timeout_s)"

# (case, task, config, repeating?, kind, attempt1, attempt2) — attempts map files -> changed files
CASES = [
    ("T1", "sem-dev-01", "focused", True, "same-fn repeat, no progress",
     lambda f: calib("sem-dev-01", "focused", 1), lambda f: calib("sem-dev-01", "focused", 2)),
    ("T2", "sem-dev-02", "focused", True, "SHRINKING HACK",
     lambda f: calib("sem-dev-02", "focused", 2), lambda f: calib("sem-dev-02", "focused", 1)),
    ("T3", "sem-dev-02", "focused", True, "SHRINKING HACK",
     lambda f: calib("sem-dev-02", "focused", 2), lambda f: calib("sem-dev-02", "focused", 3)),
    ("T4", "osc-dev-01", "focused", True, "oscillating repeat",
     lambda f: calib("osc-dev-01", "focused", 1), lambda f: calib("osc-dev-01", "focused", 2)),
    ("T5", "osc-dev-02", "focused", True, "oscillating repeat",
     lambda f: calib("osc-dev-02", "focused", 1), lambda f: calib("osc-dev-02", "focused", 2)),
    ("R1", "osc-dev-01", "caller", False, "REFINEMENT, shrinks, same fn",
     CAST_HACK, edit("billing/refund.py", REFUND_SEED,
                     "    gross = sum(item.quantity * item.unit_price for item in items)\n"
                     "    if isinstance(gross, float):\n"
                     "        return round(apply_tax(round(gross * 100), tax_rate) / 100 - restocking_fee, 2)\n"
                     "    return round(apply_tax(gross, tax_rate) - restocking_fee, 2)")),
    ("R2", "osc-dev-01", "caller", False, "REFINEMENT, shrinks, same fn",
     CAST_HACK, edit("billing/refund.py", REFUND_SEED,
                     "    gross_cents = round(sum(item.quantity * item.unit_price for item in items) * 100)\n"
                     "    return round((apply_tax(gross_cents, tax_rate) - restocking_fee) / 100, 2)")),
    ("R3", "osc-dev-02", "caller", False, "REFINEMENT, shrinks, same fn",
     edit("scheduler/jobs.py", JOB_SEED, "    return deadline_after(started_ms, int(job.timeout_s))"),
     edit("scheduler/jobs.py", JOB_SEED,
          "    timeout = job.timeout_s\n    if isinstance(timeout, float):\n"
          "        timeout = round(timeout * 1000)\n    return deadline_after(started_ms, timeout)")),
    ("R4", "sem-dev-02", "dependency", False, "refinement to zero, same fn",
     edit("timesheet/parsing.py", "    return int(m.group(1)) * 60 + int(m.group(1))",
          "    return int(m.group(1)) * 60"),
     edit("timesheet/parsing.py", "    return int(m.group(1)) * 60 + int(m.group(1))",
          "    return int(m.group(1)) * 60 + int(m.group(2))")),
    ("R5", "sem-dev-01", "dependency", False, "moved to newly examined code",
     edit("gradebook/stats.py", "    return round(sum(book.scores) / len(book.scores), 2)",
          "    scores = list(book.scores)\n    return round(sum(scores) / len(scores), 2)"),
     edit("gradebook/models.py",
          "    def __init__(self, course: str, scores: list[float] = []):\n"
          "        self.course = course\n        self.scores = scores",
          "    def __init__(self, course: str, scores: list[float] | None = None):\n"
          "        self.course = course\n        self.scores = list(scores) if scores is not None else []")),
]


def run_files(runner, task, files):
    ws = runner.prepare(task, state=files)
    try:
        return runner.run(ws, task.diag_cmd, 60)
    finally:
        runner.cleanup(ws)


def build_case(runner, case):
    cid, task_id, config_id, label, kind, a1, a2 = case
    task = load_task(task_id)
    seed = {p: (task.repo / p).read_text() for p in task.allowlist}
    ws = runner.prepare(task)
    base = runner.run(ws, task.diag_cmd, 60)
    shown = list(build_context(ws, base, CFG[config_id], pin_focal(ws, base)).files)
    runner.cleanup(ws)
    s1 = {**seed, **a1(seed)}
    r1 = run_files(runner, task, s1)
    rolled_back = bool(set(base.passed) - set(r1.passed))
    parent, parent_fail = (seed, base.failed) if rolled_back else (s1, r1.failed)
    s2 = {**parent, **a2(seed)}  # full-file replacement authored against the seed text
    r2 = run_files(runner, task, s2)
    views = [jev.attempt_view(1, config_id, seed, s1, base.failed, r1.failed + r1.collection_errors),
             jev.attempt_view(2, config_id, parent, s2, parent_fail, r2.failed + r2.collection_errors)]
    packet = jev.build_packet(task.goal, config_id, views, shown, budget_remaining=1)
    return {"case": cid, "task": task_id, "config": config_id, "label": label, "kind": kind,
            "rolled_back_after_1": rolled_back, "packet": packet}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=2)
    args = ap.parse_args()
    runner = LocalRunner()
    cases = [build_case(runner, c) for c in CASES]
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    print(f"{'case':<4} {'task':<11} {'config':<10} {'label':<6} {'shrank':<6} {'fns 1 -> 2':<44} kind")
    for c in cases:
        a = c["packet"]["attempts"]
        fns = f"{[x.split('::')[-1] for x in a[0]['functions_edited']]} -> {[x.split('::')[-1] for x in a[1]['functions_edited']]}"
        print(f"{c['case']:<4} {c['task']:<11} {c['config']:<10} {str(c['label']):<6} "
              f"{str(c['packet']['shrank']):<6} {fns:<44} {c['kind']}  "
              f"fail {len(a[1]['failing_before'])}->{len(a[1]['failing_after'])}")

    cost = 0.0
    for c in cases:
        c["p"] = {}
        for ph in jev.PHRASINGS:
            c["p"][ph] = []
            for s in range(args.samples):
                r = jev.ask(c["packet"], run_id=f"jev-smoke-{stamp}-{c['case']}-{ph}-{s}", phase="dev",
                            attempt_n=2, phrasing=ph)
                cost += r.cost_usd
                c["p"][ph].append(r.p_repeating)

    print(f"\n{'case':<4} {'label':<6} " + "  ".join(f"{ph:>11}" for ph in jev.PHRASINGS) + "   kind")
    for c in cases:
        print(f"{c['case']:<4} {str(c['label']):<6} " + "  ".join(
            f"{'/'.join(f'{p:.2f}' if p is not None else ' -- ' for p in c['p'][ph]):>11}"
            for ph in jev.PHRASINGS) + f"   {c['kind']}")

    print("\nphrasing  repeats(min..max)  refinements(min..max)  gap(single samples)  "
          "hard gap(T2,T3 vs R1-R3)  THETA  correct/sample  refinements flagged")
    summary = {}
    for ph in jev.PHRASINGS:
        rep = [p for c in cases if c["label"] for p in c["p"][ph] if p is not None]
        ref = [p for c in cases if not c["label"] for p in c["p"][ph] if p is not None]
        hard_rep = [p for c in cases if c["case"] in ("T2", "T3") for p in c["p"][ph] if p is not None]
        hard_ref = [p for c in cases if c["case"] in ("R1", "R2", "R3") for p in c["p"][ph] if p is not None]
        gap = min(rep) - max(ref)
        theta = round((min(rep) + max(ref)) / 2, 3) if gap > 0 else round(
            max(sorted(set(rep + ref)), key=lambda t: sum((p >= t) for p in rep) + sum((p < t) for p in ref)), 3)
        per_sample = []
        for s in range(args.samples):
            correct = sum(((c["p"][ph][s] or 0) >= theta) == c["label"] for c in cases)
            flagged = sum(((c["p"][ph][s] or 0) >= theta) for c in cases if not c["label"])
            per_sample.append((correct, flagged))
        summary[ph] = {"gap": gap, "hard_gap": min(hard_rep) - max(hard_ref), "theta": theta,
                       "per_sample": per_sample}
        print(f"{ph:<9} {min(rep):.2f}..{max(rep):.2f}          {min(ref):.2f}..{max(ref):.2f}"
              f"              {gap:+.2f}                {min(hard_rep) - max(hard_ref):+.2f}"
              f"                   {theta:.3f}  {', '.join(f'{c}/10' for c, _ in per_sample)}"
              f"         {', '.join(str(f) for _, f in per_sample)}")
    out = ROOT / "runs" / "jev_smoke"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{stamp}.json").write_text(json.dumps({"cases": cases, "summary": summary}, indent=1))
    print(f"\njev cost ${cost:.5f}; saved runs/jev_smoke/{stamp}.json")


if __name__ == "__main__":
    main()
