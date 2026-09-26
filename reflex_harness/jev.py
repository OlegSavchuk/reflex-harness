"""Jev: the one semantic judgment (SPEC §10). "Is this the same failed strategy in a new diff?"

Control flow uses only answers.repeating.noul. failure_shape is display only.
Timeout/HTTP error -> p is None (treated as not repeating, logged as jev_unavailable).
"""
from __future__ import annotations

import difflib
import os
import time
from dataclasses import dataclass

import requests

from .context import edited_functions
from .store import log_call

URL = "https://openrouter.ai/api/alpha/decisions"
TIMEOUT_S = 30
DIFF_LINES = 60

PHRASINGS = {
    "p1": {  # SPEC §10 as planned
        "instructions": "Is the latest attempt the same strategy as an earlier failed attempt, "
                        "without using new information?",
        "criteria": {
            "true": "Edits the same code with the same idea, e.g. adjusting rounding again, with no new "
                    "context examined and no new tests passing.",
            "false": "Moves where the fix is applied, uses newly examined code, or makes measurable "
                     "test progress."}},
    "p2": {  # shrinkage is evidence, not a verdict
        "instructions": "Is the latest attempt the same strategy as the earlier failed attempt, without "
                        "using new information? Fewer failing tests does not by itself mean a new strategy.",
        "criteria": {
            "true": "Edits the same function with the same kind of change as the earlier attempt "
                    "(rounding, casting, reordering, special-casing values or adjusting results to fit "
                    "the tests), even if some tests now pass.",
            "false": "Changes the explanation of the bug: fixes the unit, format or data it receives, "
                     "or edits code the earlier attempt did not touch, using information the earlier "
                     "attempt revealed."}},
    "p3": {  # symptom vs cause
        "instructions": "Is the latest attempt another workaround of the same symptom in the same place "
                        "as the earlier failed attempt, rather than a different explanation of the bug?",
        "criteria": {
            "true": "Same place, same kind of workaround (e.g. rounding, casting, clamping, special "
                    "cases) with no new explanation of why the tests fail; shrinking failures do not "
                    "change this.",
            "false": "A different explanation of the cause (e.g. a unit or format mismatch, a wrong "
                     "helper, shared state), acted on in the same or a different place."}},
}
FAILURE_SHAPE = {"type": "choice", "instructions": "Which pattern best describes the attempts?",
                 "criteria": {"oscillation": "Fixing one test breaks another, then reverts.",
                              "no_progress": "Different edits, same failing tests.",
                              "partial_progress": "Failures shrinking."}}


def diff_excerpt(before: dict[str, str], after: dict[str, str], max_lines: int = DIFF_LINES) -> str:
    lines = []
    for path in sorted(set(before) | set(after)):
        if before.get(path) != after.get(path):
            lines += difflib.unified_diff(before.get(path, "").splitlines(), after.get(path, "").splitlines(),
                                          f"a/{path}", f"b/{path}", lineterm="", n=1)
    return "\n".join(lines[:max_lines]) + ("\n[diff truncated]" if len(lines) > max_lines else "")


def attempt_view(n: int, config_id: str, before: dict[str, str], after: dict[str, str],
                 failing_before: list[str], failing_after: list[str]) -> dict:
    short = lambda ids: [i.split("::")[-1] for i in ids]  # noqa: E731
    return {"attempt": n, "config": config_id, "functions_edited": edited_functions(before, after),
            "diff": diff_excerpt(before, after), "failing_before": short(failing_before),
            "failing_after": short(failing_after)}


def build_packet(goal: str, config_id: str, attempts: list[dict], context_examined: list[str],
                 budget_remaining: int) -> dict:
    latest = attempts[-1]
    fb, fa = set(latest["failing_before"]), set(latest["failing_after"])
    return {"goal": goal, "current_config": config_id, "attempts": attempts[-2:],
            "context_examined": context_examined, "budget_remaining": budget_remaining,
            "failing_before": sorted(fb), "failing_after": sorted(fa), "shrank": fa < fb}


@dataclass
class JevResult:
    p_repeating: float | None
    failure_shape: str | None
    cost_usd: float
    error: str | None


def ask(packet: dict, *, run_id: str, phase: str, attempt_n: int, phrasing: str,
        model: str | None = None) -> JevResult:
    model = model or os.environ.get("JEV_MODEL", "typesafe/jev-1.13")
    q = PHRASINGS[phrasing]
    body = {"model": model, "state": packet, "questions": {
        "repeating": {"type": "noul", **q}, "failure_shape": FAILURE_SHAPE}}
    t0 = time.monotonic()
    j, error = {}, None
    try:
        r = requests.post(URL, timeout=TIMEOUT_S, json=body,
                          headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"})
        r.raise_for_status()
        j = r.json()
    except (requests.RequestException, ValueError) as e:
        error = f"jev_unavailable: {type(e).__name__}: {str(e)[:160]}"
    answers = j.get("answers") or {}
    p = (answers.get("repeating") or {}).get("noul")
    if error is None and p is None:
        error = "jev_unavailable: no repeating answer"
    usage = j.get("usage") or {}
    cost = usage.get("cost") or 0.0
    log_call(run_id=run_id, phase=phase, attempt_n=attempt_n, component="jev",
             model=j.get("model") or model, input_tokens=usage.get("input_tokens", 0),
             output_tokens=usage.get("output_tokens", 0), cost_usd=cost,
             latency_ms=int((time.monotonic() - t0) * 1000), phrasing=phrasing,
             p_repeating=p, error=error)
    return JevResult(p_repeating=p, failure_shape=(answers.get("failure_shape") or {}).get("choice"),
                     cost_usd=cost, error=error)
