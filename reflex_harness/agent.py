"""Coding agent: one direct OpenRouter chat call (SPEC §8). Parses JSON, logs one `calls` row.

Allowlist enforcement happens when the patch is applied (runner.apply_patch).
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

import requests

from . import prices
from .store import log_call

URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT_S = 180
MAX_TOKENS = 16000  # includes reasoning tokens

_FILES = {"type": "array", "items": {
    "type": "object", "additionalProperties": False, "required": ["path", "content"],
    "properties": {"path": {"type": "string"}, "content": {"type": "string"}}}}
SCHEMAS = {
    "patch": {"name": "patch", "strict": True, "schema": {
        "type": "object", "additionalProperties": False, "required": ["files", "note"],
        "properties": {"files": _FILES, "note": {"type": "string"}}}},
    "check": {"name": "check_script", "strict": True, "schema": {
        "type": "object", "additionalProperties": False, "required": ["script", "note"],
        "properties": {"script": {"type": "string"}, "note": {"type": "string"}}}},
    "narrative": {"name": "narrative", "strict": True, "schema": {
        "type": "object", "additionalProperties": False, "required": ["narrative"],
        "properties": {"narrative": {"type": "string"}}}},
}


@dataclass
class AgentReply:
    data: dict | None          # parsed JSON; None if the call failed or the reply was unparseable
    model: str                 # requested (dated) model
    model_reported: str | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    error: str | None


def parse_json(text: str) -> dict | None:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        t = t.rsplit("```", 1)[0]
    try:
        data = json.loads(t)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def call(messages: list[dict], *, run_id: str, phase: str, attempt_n: int,
         step: str = "patch", component: str = "agent", model: str | None = None) -> AgentReply:
    model = model or os.environ["CODING_MODEL"]
    body = {"model": model, "messages": messages, "temperature": 0, "max_tokens": MAX_TOKENS,
            "usage": {"include": True},
            "response_format": {"type": "json_schema", "json_schema": SCHEMAS[step]}}
    headers = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
               "Content-Type": "application/json"}
    t0 = time.monotonic()
    j, error = {}, None
    try:
        r = requests.post(URL, headers=headers, json=body, timeout=TIMEOUT_S)
        r.raise_for_status()
        j = r.json()
    except (requests.RequestException, ValueError) as e:
        error = f"{type(e).__name__}: {str(e)[:200]}"
    latency_ms = int((time.monotonic() - t0) * 1000)
    usage = j.get("usage") or {}
    in_tok, out_tok = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
    content = (j.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    data = parse_json(content) if content else None
    if error is None and data is None:
        error = f"unparseable reply: {content[:200]!r}"
    reply = AgentReply(data=data, model=model, model_reported=j.get("model"), input_tokens=in_tok,
                       output_tokens=out_tok, cost_usd=prices.cost(model, in_tok, out_tok),
                       latency_ms=latency_ms, error=error)
    log_call(run_id=run_id, phase=phase, attempt_n=attempt_n, component=component, model=model,
             input_tokens=in_tok, output_tokens=out_tok, cost_usd=reply.cost_usd,
             latency_ms=latency_ms, model_reported=reply.model_reported, step=step,
             usage_cost=usage.get("cost"),
             reasoning_tokens=(usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
             error=error)
    return reply
