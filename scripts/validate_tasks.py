"""Validate the task suite (Gate 4, structural half). No model calls.

Per task: seed fails diagnostics and protected tests; reference fix passes both; the pinned
focal resolves and matches the manifest; the files the reference fix touches are visible
only under the family's intended config (oscillation -> caller, semantic_repetition ->
dependency). Across tasks: top-level packages are unique (eval domains differ from dev).

Usage: python scripts/validate_tasks.py [task_id ...] [--load]
  --load   upsert validated tasks into the `tasks` collection (reference fix never stored)
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reflex_harness.config import CONFIGS_R1  # noqa: E402
from reflex_harness.context import build_context, pin_focal  # noqa: E402
from reflex_harness.runner import TASKS_DIR, LocalRunner, load_task  # noqa: E402

TIMEOUT_S = 60
CFG = {c["config_id"]: c for c in CONFIGS_R1}
from reflex_harness.config import DESIGNED_CONFIG as WINNER  # noqa: E402


def validate(runner, task_id):
    import json
    task = load_task(task_id)
    res = []

    def check(name, ok, detail=""):
        res.append(bool(ok))
        print(f"  {'PASS' if ok else 'FAIL'}  {name}{'  — ' + detail if detail else ''}")

    print(f"\n[{task_id}] {task.family}/{task.split}")
    check("allowlist files exist, no tests in allowlist",
          all((task.repo / p).is_file() for p in task.allowlist)
          and not any(p.startswith("tests/") for p in task.allowlist))
    seed = runner.prepare(task)
    ref = runner.prepare(task)
    try:
        base = runner.run(seed, task.diag_cmd, TIMEOUT_S)
        check("seed: diagnostics fail, some pass", base.failed and base.passed,
              f"failing={[n.split('::')[-1] for n in base.failed]} passing={len(base.passed)}")
        check("seed: protected tests fail", not runner.verify(seed, TIMEOUT_S).all_pass)
        subprocess.run(["patch", "-p1", "--batch", "--forward", "--silent", "-d", str(ref.path),
                        "-i", str(task.root / "reference.patch")], check=True)
        r = runner.run(ref, task.diag_cmd, TIMEOUT_S)
        v = runner.verify(ref, TIMEOUT_S)
        check("reference: diagnostics pass", r.all_pass, f"failed={r.failed}" if r.failed else f"{len(r.passed)} passed")
        check("reference: protected pass", v.all_pass, f"failed={v.failed}" if v.failed else f"{len(v.passed)} passed")

        pinned = pin_focal(seed, base)
        manifest = json.loads((task.root / "context_manifest.json").read_text())["focal"]
        check("pinned focal matches manifest",
              (pinned.path, pinned.function) == (manifest["path"], manifest["function"]),
              f"{pinned.path}::{pinned.function} via {pinned.source}")

        fix_files = set(re.findall(r"^\+\+\+ b/(\S+)", (task.root / "reference.patch").read_text(), re.M))
        visible = {c: fix_files <= set(build_context(seed, base, CFG[c], pinned).files)
                   for c in ("focused", "caller", "dependency")}
        want = WINNER[task.family]
        check(f"fix file visible only under {want}",
              visible[want] and not any(v for c, v in visible.items() if c != want),
              f"fix={sorted(fix_files)} visible={[c for c, v in visible.items() if v]}")
    finally:
        runner.cleanup(seed)
        runner.cleanup(ref)
    return task, all(res), pinned


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks", nargs="*")
    ap.add_argument("--load", action="store_true")
    args = ap.parse_args()
    ids = args.tasks or sorted(p.name for p in TASKS_DIR.iterdir() if (p / "task.json").is_file())
    runner = LocalRunner()
    out = [validate(runner, t) for t in ids]

    pkgs = {}
    for task, _, _ in out:
        for p in task.allowlist:
            pkgs.setdefault(p.split("/")[0], set()).add(task.task_id)
    shared = {k: sorted(v) for k, v in pkgs.items() if len(v) > 1}
    print(f"\n[suite] packages unique across tasks: {'PASS' if not shared else 'FAIL ' + str(shared)}")
    counts = {}
    for task, ok, pinned in out:
        key = (task.family, task.split)
        counts[key] = counts.get(key, 0) + 1
        print(f"  {task.task_id:<12} {task.family:<20} {task.split:<5} focal={pinned.function} "
              f"({pinned.source})  {'OK' if ok else 'INVALID'}")
    print(f"  composition: {dict(sorted((f'{f}/{s}', n) for (f, s), n in counts.items()))}")
    passed = sum(ok for _, ok, _ in out) and not shared

    if args.load and all(ok for _, ok, _ in out):
        from reflex_harness.store import db
        for task, _, _ in out:
            db()["tasks"].replace_one({"task_id": task.task_id}, {
                "task_id": task.task_id, "family": task.family, "split": task.split,
                "repo_path": str(task.repo.relative_to(TASKS_DIR.parent)),
                "allowlist": list(task.allowlist), "diag_cmd": list(task.diag_cmd),
                "protected_cmd": list(task.protected_cmd)}, upsert=True)
        print(f"  loaded {len(out)} tasks into `tasks`")
    n_ok = sum(ok for _, ok, _ in out)
    print(f"\nTasks: {'PASS' if n_ok == len(out) and not shared else 'FAIL'} ({n_ok}/{len(out)} valid)")
    sys.exit(0 if n_ok == len(out) and not shared else 1)


if __name__ == "__main__":
    main()
