"""Controller: the attempt loop and the decide() ladder (SPEC §6). Loop lands in Gate 7.

Ladder step 9 uses a rule-based same-strategy detector instead of Jev (Gate 5: Jev could
not separate same-function shrinking hacks from genuine refinements; disclosed).
"""
from __future__ import annotations


def _functions(edited: list[str]) -> set[str]:
    return {e for e in edited if not e.endswith("::<module>")}


def same_strategy(prev_edited: list[str], cur_edited: list[str], focal: str,
                  failing_after: list[str]) -> bool:
    """Same focal function edited on consecutive attempts, no change in which functions are
    edited, failures not reduced to zero. `focal` and edits are "path::name"."""
    prev, cur = _functions(prev_edited), _functions(cur_edited)
    return focal in prev and focal in cur and prev == cur and bool(failing_after)


def progress_moved(prev_edited: list[str], cur_edited: list[str], failing_before: list[str],
                   failing_after: list[str]) -> bool:
    """Ladder step 7: strict-subset shrinkage AND the patch edited a function the previous
    attempt did not. Only then continue without the same-strategy check."""
    return (set(failing_after) < set(failing_before)
            and bool(_functions(cur_edited) - _functions(prev_edited)))


# ---------- one attempt under one config (shared by memory building and the loop) ----------

import hashlib  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402

from . import agent  # noqa: E402
from .context import PinnedFocal, build_context, edited_functions, render  # noqa: E402
from .runner import (LocalRunner, PatchRejected, RunnerError, TestReport, Workspace,  # noqa: E402
                     apply_patch, snapshot)
from .store import insert_attempt  # noqa: E402

TEST_TIMEOUT_S = 120
SCRIPT_TIMEOUT_S = 60


@dataclass
class AttemptResult:
    config_id: str
    focal_source: str
    parent_files: dict
    files: dict
    report: TestReport
    edited: list[str]
    patch: dict | None
    note: str | None
    cost_usd: float
    regressed: list[str]
    solved: bool
    verified: bool
    error: str | None = None
    infra_error: bool = False
    context_files: list[str] = field(default_factory=list)


def patch_fingerprint(patch: dict | None) -> str:
    files = sorted((f["path"], f["content"]) for f in (patch or {}).get("files", []))
    return hashlib.sha256(repr(files).encode()).hexdigest()


def restore(ws: Workspace, files: dict) -> None:
    """Roll back to a snapshot of allowlisted files."""
    apply_patch(ws, {"files": [{"path": p, "content": c} for p, c in files.items()]})


def run_attempt(runner: LocalRunner, ws: Workspace, parent_report: TestReport, config: dict,
                pinned: PinnedFocal, prior: list[str], *, run_id: str, phase: str,
                attempt_n: int, verify: bool = True) -> AttemptResult:
    """Build context, call the model (two calls for diagnostic), apply, test, verify."""
    task = ws.task
    parent_files = snapshot(ws)
    ctx = build_context(ws, parent_report, config, pinned)
    cost, check, note, patch, error = 0.0, None, None, None, None
    if config["workflow"]["diagnostic_first"]:
        r1 = agent.call(render(ctx, task.goal, prior, step="check"), run_id=run_id, phase=phase,
                        attempt_n=attempt_n, step="check")
        cost += r1.cost_usd
        script = (r1.data or {}).get("script") or ""
        out = runner.run_script(ws, script, SCRIPT_TIMEOUT_S).output if script else f"<no script: {r1.error}>"
        check = (script, out)
    reply = agent.call(render(ctx, task.goal, prior, step="patch", check=check), run_id=run_id,
                       phase=phase, attempt_n=attempt_n)
    cost += reply.cost_usd
    report = parent_report
    if reply.data is None:
        error = reply.error
    else:
        note = reply.data.get("note")
        try:
            apply_patch(ws, reply.data)
            patch = reply.data
        except (PatchRejected, KeyError, TypeError) as e:
            error = f"patch rejected: {e}"
    try:
        if patch is not None:
            report = runner.run(ws, task.diag_cmd, TEST_TIMEOUT_S)
        solved = patch is not None and report.all_pass
        verified = bool(solved and verify and runner.verify(ws, TEST_TIMEOUT_S).all_pass)
    except RunnerError as e:
        return AttemptResult(config["config_id"], ctx.focal_source, parent_files, snapshot(ws),
                             parent_report, [], patch, note, cost, [], False, False,
                             error=f"infra: {e}", infra_error=True, context_files=list(ctx.files))
    files = snapshot(ws)
    return AttemptResult(
        config_id=config["config_id"], focal_source=ctx.focal_source, parent_files=parent_files,
        files=files, report=report, edited=edited_functions(parent_files, files), patch=patch,
        note=note, cost_usd=cost, regressed=sorted(set(parent_report.passed) - set(report.passed)),
        solved=solved, verified=verified, error=error, context_files=list(ctx.files))


def summarize(n: int, a: AttemptResult, rolled_back: bool) -> str:
    """Prior-attempt line shown to later attempts. Same format for memory trials and eval."""
    short = lambda ids: ", ".join(i.split("::")[-1] for i in ids) or "none"  # noqa: E731
    fns = ", ".join(e.split("::")[-1] for e in a.edited if not e.endswith("<module>")) or "nothing"
    if a.error and a.patch is None:
        return f"Attempt {n} ({a.config_id}): no patch applied ({a.error[:120]})."
    line = (f"Attempt {n} ({a.config_id}): edited {fns}"
            f"{f' — {a.note}' if a.note else ''}. Failing after: {short(a.report.failed)}.")
    if a.regressed:
        line += f" Regression: {short(a.regressed)} broke" + ("; rolled back." if rolled_back else ".")
    return line


def record(a: AttemptResult, *, run_id: str, phase: str, mode: str, task_id: str, attempt_n: int,
           rolled_back: bool, trigger: str | None = None) -> None:
    insert_attempt({
        "run_id": run_id, "phase": phase, "mode": mode, "task_id": task_id, "attempt_n": attempt_n,
        "config_id": a.config_id, "focal_source": a.focal_source,
        "parent_state_hash": _hash(a.parent_files), "state_hash": _hash(a.files),
        "patch": a.patch, "patch_fingerprint": patch_fingerprint(a.patch),
        "failed_tests": a.report.failed + a.report.collection_errors, "passed_tests": a.report.passed,
        "diag_pass": a.solved, "verified": a.verified, "regression": bool(a.regressed),
        "rolled_back": rolled_back, "trigger": trigger, "jev_p_repeating": None,
        "cost_usd": a.cost_usd, "error": a.error})


def _hash(files: dict) -> str:
    h = hashlib.sha256()
    for p in sorted(files):
        h.update(p.encode() + b"\0" + files[p].encode() + b"\0")
    return h.hexdigest()


# ---------- the loop (SPEC §6) ----------

import math  # noqa: E402
import time as _time  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

from . import config as _config  # noqa: E402
from . import jev as _jev  # noqa: E402
from . import prices  # noqa: E402
from .context import pin_focal  # noqa: E402
from .narrator import error_symbols, forbidden_tokens, narrate  # noqa: E402
from .pipelines import retrieval_pipeline, selection_pipeline  # noqa: E402
from .runner import load_task  # noqa: E402
from .store import db, log_call  # noqa: E402

BUDGET = 3
ARMS = ("plain_retry", "fallback", "memory")


def _log_embed(run_id: str, phase: str, attempt_n: int, text: str, latency_ms: int) -> None:
    tokens = math.ceil(len(text) / 4)  # estimate (SPEC §13.2); Automated Embedding reports no usage
    log_call(run_id=run_id, phase=phase, attempt_n=attempt_n, component="embed",
             model=_config.EMBED_MODEL, input_tokens=tokens, output_tokens=0,
             cost_usd=tokens * prices.VOYAGE_4_PER_TOKEN, latency_ms=latency_ms, estimated=True)


def intervene(arm: str, *, task, run_id: str, phase: str, attempt_n: int, trigger: str,
              configs: dict, pinned, history: list, snapshot: str, registry: str,
              protocol: str) -> str | None:
    """Pick the next config and write one `decisions` row. None = configurations exhausted."""
    tried = db()["attempts"].distinct("config_id", {"run_id": run_id})  # exact task history
    untried = sorted((c for c in configs.values() if c["config_id"] not in tried), key=lambda c: c["order"])
    row = {"run_id": run_id, "task_id": task.task_id, "attempt_n": attempt_n, "trigger": trigger,
           "policy": arm, "tried_config_ids": tried}
    if arm == "fallback":
        chosen = untried[0]["config_id"] if untried else None
        row.update(retrieved=[], candidates=[{"_id": c["config_id"], "order": c["order"]} for c in untried],
                   chosen_config_id=chosen, status="selected" if chosen else "configurations_exhausted")
    else:
        views = [_jev.attempt_view(i + 1, a.config_id, a.parent_files, a.files, fb,
                                   a.report.failed + a.report.collection_errors)
                 for i, (a, fb) in enumerate(history)]
        symbols = error_symbols(views, pinned.function, [a.report for a, _ in history])
        narrative, violations, _ = narrate(views, forbidden_tokens(task.repo, task.allowlist, symbols),
                                           run_id=run_id, phase=phase, attempt_n=attempt_n)
        ckpt = db()["checkpoints"]
        t0 = _time.monotonic()
        retrieved = list(ckpt.aggregate(retrieval_pipeline(narrative, symbols, snapshot, protocol)))
        _log_embed(run_id, phase, attempt_n, narrative, int((_time.monotonic() - t0) * 1000))
        t0 = _time.monotonic()
        rows = list(ckpt.aggregate(selection_pipeline(narrative, symbols, snapshot, protocol, registry, tried)))
        _log_embed(run_id, phase, attempt_n, narrative, int((_time.monotonic() - t0) * 1000))
        if not rows:
            status, chosen = "configurations_exhausted", None
        elif len(retrieved) < 2:
            status, chosen = "insufficient_evidence", (untried[0]["config_id"] if untried else None)
        else:
            status, chosen = "selected", rows[0]["_id"]
        row.update(narrative=narrative, narrative_violations=violations, error_symbols=symbols,
                   retrieved=[{"checkpoint_id": r["checkpoint_id"], "family": r.get("family"),
                               "failure_narrative": r.get("failure_narrative"),
                               "fusion_score": (r.get("fusion") or {}).get("value")} for r in retrieved],
                   candidates=rows, chosen_config_id=chosen, status=status)
    db()["decisions"].insert_one({**row, "created_at": datetime.now(timezone.utc)})
    return row["chosen_config_id"]


def run_task(task_id: str, arm: str, *, phase: str, snapshot: str = _config.SNAPSHOT_ID,
             registry: str = _config.REGISTRY, protocol: str = _config.PROTOCOL,
             run_id: str | None = None, log=print) -> dict:
    """One task under one arm. Returns the `runs` document."""
    assert arm in ARMS and phase in ("dev", "eval")
    task = load_task(task_id)
    runner = LocalRunner()
    run_id = run_id or f"{phase}-{arm}-{task_id}-{_time.strftime('%Y%m%dT%H%M%S', _time.gmtime())}"
    configs = {c["config_id"]: c for c in db()["configs"].find({"registry": registry}, {"_id": 0})}
    ws = runner.prepare(task)
    stop, switched, in_cfg, n = None, False, 0, 0
    try:
        cur = runner.run(ws, task.diag_cmd, TEST_TIMEOUT_S)
        pinned = pin_focal(ws, cur)
        focal_key = f"{pinned.path}::{pinned.function}"
        cfg = configs["focused"]
        prior, history, cfg_history = [], [], []
        seen_states, seen_fps = set(), set()
        for n in range(1, BUDGET + 1):
            parent = cur
            a = run_attempt(runner, ws, parent, cfg, pinned, prior, run_id=run_id, phase=phase,
                            attempt_n=n, verify=False)
            if a.infra_error:
                record(a, run_id=run_id, phase=phase, mode=arm, task_id=task_id, attempt_n=n, rolled_back=False)
                stop = "infrastructure_error"
                break
            in_cfg += 1
            trigger, rolled = None, False
            if a.solved:                                                   # 1. diagnostics pass
                a.verified = runner.verify(ws, TEST_TIMEOUT_S).all_pass
                record(a, run_id=run_id, phase=phase, mode=arm, task_id=task_id, attempt_n=n, rolled_back=False)
                stop = "solved" if a.verified else "verification_failed"
                log(f"  attempt {n} [{cfg['config_id']}] diagnostics pass -> {stop}")
                break
            if arm != "plain_retry":
                if a.regressed:                                            # 2. regression
                    restore(ws, a.parent_files)
                    rolled, trigger = True, "regression"
                else:
                    cur = a.report
                fp = (patch_fingerprint(a.patch), _hash(a.parent_files))
                if trigger is None and a.patch is not None and (_hash(a.files) in seen_states or fp in seen_fps):
                    trigger = "exact_repeat"                               # 6. exact repeat
                if a.patch is not None:
                    seen_states.add(_hash(a.files))
                    seen_fps.add(fp)
                prev = cfg_history[-1] if cfg_history else None
                failing_after = a.report.failed + a.report.collection_errors
                if (trigger is None and prev is not None                   # 7. progress that moved
                        and not progress_moved(prev.edited, a.edited, parent.failed, failing_after)
                        and not switched and in_cfg >= 2                   # 8. too early
                        and same_strategy(prev.edited, a.edited, focal_key, failing_after)):
                    trigger = "same_strategy"                              # 9. same strategy
            else:
                cur = a.report
            record(a, run_id=run_id, phase=phase, mode=arm, task_id=task_id, attempt_n=n,
                   rolled_back=rolled, trigger=trigger)
            history.append((a, parent.failed))
            cfg_history.append(a)
            prior.append(summarize(n, a, rolled))
            log(f"  attempt {n} [{cfg['config_id']}] failing={len(a.report.failed)} "
                f"regressed={len(a.regressed)} edited={[e.split('::')[-1] for e in a.edited]}"
                f"{' rolled back' if rolled else ''}{' trigger=' + trigger if trigger else ''}")
            if n == BUDGET:                                                # 3. budget
                stop = "rolled_back_budget_exhausted" if rolled else "budget_exhausted"
                break
            if trigger:
                if switched:                                               # 4. one switch per task
                    stop = "intervention_limit_reached"
                    break
                chosen = intervene(arm, task=task, run_id=run_id, phase=phase, attempt_n=n,  # 5.
                                   trigger=trigger, configs=configs, pinned=pinned, history=history,
                                   snapshot=snapshot, registry=registry, protocol=protocol)
                if chosen is None:
                    stop = "configurations_exhausted"
                    break
                log(f"  -> switch {cfg['config_id']} -> {chosen} ({arm})")
                cfg, switched, in_cfg, cfg_history = configs[chosen], True, 0, []
    finally:
        runner.cleanup(ws)
    cost = next(db()["calls"].aggregate([{"$match": {"run_id": run_id}},
                                         {"$group": {"_id": None, "c": {"$sum": "$cost_usd"}}}]), {"c": 0.0})["c"]
    doc = {"run_id": run_id, "phase": phase, "arm": arm, "task_id": task_id, "family": task.family,
           "stop_reason": stop, "verified_fix": stop == "solved", "attempts": n, "switched": switched,
           "configs_used": db()["attempts"].distinct("config_id", {"run_id": run_id}),
           "cost_usd": cost, "snapshot_id": snapshot if arm == "memory" else None,
           "created_at": datetime.now(timezone.utc)}
    db()["runs"].insert_one(dict(doc))
    return doc
