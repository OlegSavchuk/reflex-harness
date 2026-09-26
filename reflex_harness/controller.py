"""Controller: the attempt loop and the decide() ladder (SPEC §6). Loop lands in Gate 7.

Ladder step 9 uses a rule-based same-strategy detector instead of Jev (Gate 5: Jev could
not separate same-function shrinking hacks from genuine refinements; disclosed).
"""
from __future__ import annotations


def same_strategy(prev_edited: list[str], cur_edited: list[str], region,
                  failing_after: list[str]) -> bool:
    """Ladder step 9: both attempts' edits stay inside the focal region and failures remain."""
    return bool(failing_after) and all(region.inside(e) for e in [*prev_edited, *cur_edited])


def progress_moved(cur_edited: list[str], failing_before: list[str], failing_after: list[str],
                   region) -> bool:
    """Ladder step 7: strict-subset shrinkage AND the edit lies outside the focal region.
    Only then continue without the same-strategy check."""
    return set(failing_after) < set(failing_before) and any(not region.inside(e) for e in cur_edited)


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
    prompt: str = ""          # user message of the patch call (as the model saw it)


def patch_fingerprint(patch: dict | None) -> str:
    files = sorted((f["path"], f["content"]) for f in (patch or {}).get("files", []))
    return hashlib.sha256(repr(files).encode()).hexdigest()


def restore(ws: Workspace, files: dict) -> None:
    """Roll back to a snapshot of allowlisted files."""
    apply_patch(ws, {"files": [{"path": p, "content": c} for p, c in files.items()]})


def run_attempt(runner: LocalRunner, ws: Workspace, parent_report: TestReport, config: dict,
                pinned: PinnedFocal, prior: list[str], *, run_id: str, phase: str,
                attempt_n: int, verify: bool = True, reset_note: bool = False,
                replay: "AttemptResult | None" = None) -> AttemptResult:
    """Build context, call the model (two calls for diagnostic), apply, test, verify.
    replay: reuse a shared attempt's model output (same prompt) instead of a new call;
    its cost was logged once under the shared run id."""
    task = ws.task
    parent_files = snapshot(ws)
    ctx = build_context(ws, parent_report, config, pinned)
    cost, check, note, patch, error = 0.0, None, None, None, None
    if replay is not None:
        assert not config["workflow"]["diagnostic_first"], "only single-call attempts are shared"
        messages = [{"role": "system", "content": ""}, {"role": "user", "content": replay.prompt}]
        data = {"files": replay.patch["files"], "note": replay.note} if replay.patch else None
        reply = agent.AgentReply(data=data, model="replay", model_reported=None,
                                 input_tokens=0, output_tokens=0, cost_usd=replay.cost_usd,
                                 latency_ms=0, error=None if data else replay.error)
    elif config["workflow"]["diagnostic_first"]:
        r1 = agent.call(render(ctx, task.goal, prior, step="check", reset_note=reset_note),
                        run_id=run_id, phase=phase, attempt_n=attempt_n, step="check")
        cost += r1.cost_usd
        script = (r1.data or {}).get("script") or ""
        out = runner.run_script(ws, script, SCRIPT_TIMEOUT_S).output if script else f"<no script: {r1.error}>"
        check = (script, out)
    if replay is None:
        messages = render(ctx, task.goal, prior, step="patch", check=check, reset_note=reset_note)
        reply = agent.call(messages, run_id=run_id, phase=phase, attempt_n=attempt_n)
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
                             error=f"infra: {e}", infra_error=True, context_files=list(ctx.files),
                             prompt=messages[1]["content"])
    files = snapshot(ws)
    return AttemptResult(
        config_id=config["config_id"], focal_source=ctx.focal_source, parent_files=parent_files,
        files=files, report=report, edited=edited_functions(parent_files, files), patch=patch,
        note=note, cost_usd=cost, regressed=sorted(set(parent_report.passed) - set(report.passed)),
        solved=solved, verified=verified, error=error, context_files=list(ctx.files),
        prompt=messages[1]["content"])


def summarize(n: int, a: AttemptResult, rolled_back: bool) -> str:
    """Prior-attempt line shown to later attempts. Same format for memory trials and eval."""
    short = lambda ids: ", ".join(i.split("::")[-1] for i in ids) or "none"  # noqa: E731
    fns = ", ".join(e.split("::")[-1] for e in a.edited if not e.endswith("<module>")) or "nothing"
    if a.error and a.patch is None:
        return f"Attempt {n} ({a.config_id}): no patch applied ({a.error[:120]})."
    line = (f"Attempt {n} ({a.config_id}): edited {fns}"
            f"{f' — ' + a.note.rstrip(' .') if a.note else ''}. Failing after: {short(a.report.failed)}.")
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
        "cost_usd": a.cost_usd, "error": a.error, "prompt": a.prompt})


def _hash(files: dict) -> str:
    h = hashlib.sha256()
    for p in sorted(files):
        h.update(p.encode() + b"\0" + files[p].encode() + b"\0")
    return h.hexdigest()


# ---------- the loop (SPEC §6) ----------

import random  # noqa: E402
import time as _time  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

from . import config as _config  # noqa: E402
from .context import focal_region, pin_focal  # noqa: E402
from .queries import load_query, query_input  # noqa: E402
from .pipelines import retrieval_pipeline, selection_pipeline  # noqa: E402
from .runner import DirtyTreeError, load_task, reset_to_seed, tree_hash  # noqa: E402
from .store import db, log_call  # noqa: E402

BUDGET = 3
ARMS = ("plain_retry", "fallback", "random", "memory")


def random_seed(task_id: str, repeat: int) -> int:
    """Seed for the `random` arm: sha256(task_id:repeat), stable across processes."""
    return int(hashlib.sha256(f"{task_id}:{repeat}".encode()).hexdigest()[:16], 16)


def select_next(arm: str, *, task, run_id: str, phase: str, attempt_n: int, trigger: str,
                configs: dict, snapshot: str, registry: str, protocol: str,
                repeat: int = 0) -> dict:
    """Pick the next config. Returns the decisions row (not yet written);
    row["chosen_config_id"] is None when configurations are exhausted."""
    tried = db()["attempts"].distinct("config_id", {"run_id": run_id})  # exact task history
    untried = sorted((c for c in configs.values() if c["config_id"] not in tried), key=lambda c: c["order"])
    row = {"run_id": run_id, "task_id": task.task_id, "attempt_n": attempt_n, "trigger": trigger,
           "policy": arm, "tried_config_ids": tried}
    if arm == "fallback":
        chosen = untried[0]["config_id"] if untried else None
        row.update(retrieved=[], candidates=[{"_id": c["config_id"], "order": c["order"]} for c in untried],
                   chosen_config_id=chosen, status="selected" if chosen else "configurations_exhausted")
    elif arm == "random":  # uniform over untried configs (registry order), seeded per (task, repeat)
        seed = random_seed(task.task_id, repeat)
        chosen = random.Random(seed).choice([c["config_id"] for c in untried]) if untried else None
        row.update(retrieved=[], candidates=[{"_id": c["config_id"], "order": c["order"]} for c in untried],
                   random_seed=seed, repeat=repeat, chosen_config_id=chosen,
                   status="selected" if chosen else "configurations_exhausted")
    else:
        q = load_query(task)  # fixed per task (tasks/<id>/query.json); the narrator never runs here
        narrative, symbols, violations = q["narrative"], q["error_symbols"], q["narrative_violations"]
        query = query_input(q)
        ckpt = db()["checkpoints"]  # stored int8 query vector: no embedding call at eval time
        retrieved = list(ckpt.aggregate(retrieval_pipeline(query, snapshot, protocol)))
        rows = list(ckpt.aggregate(selection_pipeline(query, snapshot, protocol, registry, tried)))
        if not rows:
            status, chosen = "configurations_exhausted", None
        elif len(retrieved) < 2:
            status, chosen = "insufficient_evidence", (untried[0]["config_id"] if untried else None)
        else:
            status, chosen = "selected", rows[0]["_id"]
        top = [{"rank": i, "checkpoint_id": r["checkpoint_id"], "family": r.get("family"),
                "failure_narrative": r.get("failure_narrative"), "semantic_score": r.get("semantic_score")}
               for i, r in enumerate(retrieved, 1)]
        sem = [t["semantic_score"] for t in top]
        row.update(narrative=narrative, narrative_violations=violations, error_symbols=symbols,
                   query_sha256=q["query_sha256"], retrieved=top,
                   candidates=rows, chosen_config_id=chosen, status=status)
        # diagnostics; same margin definition as Gate 8 (top-1 minus top-2 semantic score)
        row["retrieval"] = {
            "query_sha256": q["query_sha256"], "embedding_sha256": q["embedding"]["sha256"],
            "semantic_margin": (sem[0] - sem[1]) if len(sem) > 1 and None not in sem[:2] else None}
    return row


def switch_strategy(ws, row: dict, from_config: str) -> None:
    """The one shared switch path (every arm that switches): reset the worktree to the seed
    (`git checkout -- .` + `git clean -fd`), assert the tree hash equals the seed hash, and
    write the decisions row with the reset evidence. Raises DirtyTreeError on mismatch."""
    try:
        tree, verified = reset_to_seed(ws), True
    except DirtyTreeError:
        tree, verified = tree_hash(ws.path), False
    row["reset"] = {"from_config": from_config, "to_config": row["chosen_config_id"],
                    "seed_hash": ws.seed_hash, "tree_hash": tree, "seed_hash_verified": verified}
    db()["decisions"].insert_one({**row, "created_at": datetime.now(timezone.utc)})
    if not verified:
        raise DirtyTreeError(f"{row['task_id']}: reset to seed failed (tree {tree[:12]} != "
                             f"seed {ws.seed_hash[:12]}); run stopped, never continue on a dirty tree")


def shared_first_attempt(task_id: str, *, phase: str, run_id: str,
                         registry: str = _config.REGISTRY) -> AttemptResult:
    """Attempt 1 (focused, no history) generated once per task and replayed by every arm, so
    arms differ only after attempt 1. One `calls` row, under `run_id`."""
    task = load_task(task_id)
    runner = LocalRunner()
    cfg = db()["configs"].find_one({"registry": registry, "config_id": "focused"}, {"_id": 0})
    ws = runner.prepare(task)
    try:
        base = runner.run(ws, task.diag_cmd, TEST_TIMEOUT_S)
        return run_attempt(runner, ws, base, cfg, pin_focal(ws, base), [], run_id=run_id,
                           phase=phase, attempt_n=1, verify=False)
    finally:
        runner.cleanup(ws)


def selection_log(arm: str, family: str, stop: str | None, switch_at: int | None,
                  triggers: list, row: dict | None, last_n: int) -> dict:
    """Per-run fields for Gate 8 reporting (SPEC §13.4)."""
    designed = _config.DESIGNED_CONFIG.get(family)
    chosen = (row or {}).get("chosen_config_id")
    if arm == "plain_retry":
        pre = "arm_has_no_selection"
    elif switch_at is not None or stop == "configurations_exhausted":
        pre = None
    elif stop in ("solved", "verification_failed"):
        pre = f"diagnostics_passed_before_switch ({stop})"
    elif stop in ("budget_exhausted", "rolled_back_budget_exhausted"):
        pre = "trigger_at_final_attempt" if any(t["attempt_n"] == last_n for t in triggers) else "no_trigger"
    else:
        pre = stop
    neighbours = [{"rank": i, "checkpoint_id": r["checkpoint_id"], "family": r.get("family"),
                   "semantic_score": r.get("semantic_score")}
                  for i, r in enumerate((row or {}).get("retrieved") or [], 1)] or None
    retrieval = (row or {}).get("retrieval") or {}
    return {"switch_attempt": switch_at, "triggers": triggers, "neighbours": neighbours,
            "random_seed": (row or {}).get("random_seed"),
            "query_sha256": retrieval.get("query_sha256"),
            "embedding_sha256": retrieval.get("embedding_sha256"),
            "semantic_margin": retrieval.get("semantic_margin"),
            "chosen_config": chosen, "designed_config": designed,
            "chosen_matches_designed": (chosen == designed) if chosen else None,
            "pre_selection_end": pre}


def run_task(task_id: str, arm: str, *, phase: str, snapshot: str = _config.SNAPSHOT_ID,
             registry: str = _config.REGISTRY, protocol: str = _config.PROTOCOL,
             run_id: str | None = None, first_attempt: AttemptResult | None = None,
             shared_run_id: str | None = None, repeat: int = 0, log=print) -> dict:
    """One task under one arm. Returns the `runs` document.
    first_attempt: shared attempt 1 to replay (see shared_first_attempt)."""
    assert arm in ARMS and phase in ("dev", "eval")
    task = load_task(task_id)
    runner = LocalRunner()
    run_id = run_id or f"{phase}-{arm}-{task_id}-{_time.strftime('%Y%m%dT%H%M%S', _time.gmtime())}"
    configs = {c["config_id"]: c for c in db()["configs"].find({"registry": registry}, {"_id": 0})}
    ws = runner.prepare(task)
    stop, switched, in_cfg, n, reset_note, dirty = None, False, 0, 0, False, None
    switch_at, chosen_row, triggers = None, None, []
    try:
        base = cur = runner.run(ws, task.diag_cmd, TEST_TIMEOUT_S)
        pinned = pin_focal(ws, cur)
        region = focal_region(ws, pinned, base)
        cfg = configs["focused"]
        prior, cfg_history = [], []
        seen_states, seen_fps = set(), set()
        for n in range(1, BUDGET + 1):
            parent = cur
            a = run_attempt(runner, ws, parent, cfg, pinned, prior, run_id=run_id, phase=phase,
                            attempt_n=n, verify=False, reset_note=reset_note,
                            replay=first_attempt if n == 1 else None)
            reset_note = False
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
                        and not progress_moved(a.edited, parent.failed, failing_after, region)
                        and not switched and in_cfg >= 2                   # 8. too early
                        and same_strategy(prev.edited, a.edited, region, failing_after)):
                    trigger = "same_strategy"                              # 9. same strategy
            else:
                cur = a.report
            record(a, run_id=run_id, phase=phase, mode=arm, task_id=task_id, attempt_n=n,
                   rolled_back=rolled, trigger=trigger)
            if trigger:
                triggers.append({"attempt_n": n, "trigger": trigger})
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
                row = select_next(arm, task=task, run_id=run_id, phase=phase, attempt_n=n,  # 5.
                                  trigger=trigger, configs=configs, snapshot=snapshot,
                                  registry=registry, protocol=protocol, repeat=repeat)
                chosen, chosen_row = row["chosen_config_id"], row
                if chosen is None:
                    db()["decisions"].insert_one({**row, "created_at": datetime.now(timezone.utc)})
                    stop = "configurations_exhausted"
                    break
                try:
                    switch_strategy(ws, row, cfg["config_id"])
                except DirtyTreeError as e:
                    stop, dirty = "reset_failed", e
                    break
                log(f"  -> switch {cfg['config_id']} -> {chosen} ({arm}); reset to seed, hash verified")
                cfg, switched, in_cfg, cfg_history = configs[chosen], True, 0, []
                cur, reset_note, switch_at = base, True, n
    finally:
        runner.cleanup(ws)
    # all calls of the run count, including abandoned attempts and the narrator
    tot = next(db()["calls"].aggregate([{"$match": {"run_id": run_id}}, {"$group": {
        "_id": None, "c": {"$sum": "$cost_usd"}, "i": {"$sum": "$input_tokens"},
        "o": {"$sum": "$output_tokens"}}}]), {"c": 0.0, "i": 0, "o": 0})
    doc = {"run_id": run_id, "phase": phase, "arm": arm, "task_id": task_id, "family": task.family,
           "repeat": repeat,
           "stop_reason": stop, "verified_fix": stop == "solved", "attempts": n, "switched": switched,
           "configs_used": db()["attempts"].distinct("config_id", {"run_id": run_id}),
           "cost_usd": tot["c"] + (first_attempt.cost_usd if first_attempt else 0.0),
           "input_tokens": tot["i"], "output_tokens": tot["o"],
           "shared_attempt": ({"run_id": shared_run_id, "cost_usd": first_attempt.cost_usd}
                              if first_attempt else None),
           "snapshot_id": snapshot if arm == "memory" else None,
           **selection_log(arm, task.family, stop, switch_at, triggers, chosen_row, n),
           "created_at": datetime.now(timezone.utc)}
    db()["runs"].insert_one(dict(doc))
    if dirty:
        raise dirty
    return doc
