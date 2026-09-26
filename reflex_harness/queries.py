"""Fixed retrieval query per task (Gate 9, Phase 1).

The query (narrative + error_symbols) is generated ONCE per task from the seed code and seed
failing tests, stored in tasks/<id>/query.json with its sha256, and reused for every run and
repeat. Its embedding is also computed once (voyage-4, input_type=query, int8 — the index's
model and quantization) and stored with its own sha256; retrieval passes it as a BSON int8
`queryVector`, so repeated retrievals are bit-identical. Neither the narrator nor an embedding
call runs at eval time; a missing or altered query file stops the run.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone

import requests
from bson.binary import Binary, BinaryVectorDtype

from . import config, prices

from .context import pin_focal
from .narrator import NARRATOR_SYSTEM, forbidden_tokens, narrate_task, task_symbols
from .runner import LocalRunner, Task
from .store import log_call

QUERY_FILE = "query.json"


class QueryError(Exception):
    """The task has no stored query, or the stored query does not match its recorded hash."""


def query_sha256(narrative: str, error_symbols: str) -> str:
    blob = json.dumps({"narrative": narrative, "error_symbols": error_symbols}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def load_query(task: Task) -> dict:
    path = task.root / QUERY_FILE
    if not path.is_file():
        raise QueryError(f"{task.task_id}: no {QUERY_FILE}; run scripts/make_queries.py (never at eval time)")
    q = json.loads(path.read_text())
    if query_sha256(q["narrative"], q["error_symbols"]) != q["query_sha256"]:
        raise QueryError(f"{task.task_id}: {QUERY_FILE} does not match its recorded sha256")
    emb = q.get("embedding")
    if emb is not None and embedding_sha256(emb["vector"]) != emb["sha256"]:
        raise QueryError(f"{task.task_id}: stored query embedding does not match its sha256")
    return q


def embedding_sha256(vector: list[int]) -> str:
    return hashlib.sha256(json.dumps(vector).encode()).hexdigest()


def query_input(q: dict) -> Binary:
    """What $vectorSearch receives: the stored int8 embedding as a BSON vector (queryVector)."""
    emb = q.get("embedding")
    if emb is None:
        raise QueryError(f"{q['task_id']}: stored query has no embedding; run make_queries.py --embed-missing")
    return Binary.from_vector(emb["vector"], BinaryVectorDtype.INT8)


def embed_query(text: str, *, run_id: str, input_type: str = "query") -> dict:
    """One Voyage call: voyage-4, int8 (the index's model and quantization); input_type "query"
    for stored queries ("document" only to compare with the memory side). Writes one `calls` row
    (component "embed")."""
    t0 = time.monotonic()
    r = requests.post(f"{os.environ.get('VOYAGE_BASE_URL', 'https://ai.mongodb.com/v1')}/embeddings",
                      timeout=30, headers={"Authorization": f"Bearer {os.environ['VOYAGE_API_KEY']}"},
                      json={"input": [text], "model": config.EMBED_MODEL, "input_type": input_type,
                            "output_dtype": config.QUERY_DTYPE})
    r.raise_for_status()
    j = r.json()
    vec = j["data"][0]["embedding"]
    tokens = (j.get("usage") or {}).get("total_tokens", 0)
    log_call(run_id=run_id, phase="dev", attempt_n=0, component="embed", model=config.EMBED_MODEL,
             input_tokens=tokens, output_tokens=0, cost_usd=tokens * prices.VOYAGE_4_PER_TOKEN,
             latency_ms=int((time.monotonic() - t0) * 1000), input_type=input_type,
             output_dtype=config.QUERY_DTYPE)
    if len(vec) != config.EMBED_DIMS:
        raise QueryError(f"embedding has {len(vec)} dims, index expects {config.EMBED_DIMS}")
    return {"model": config.EMBED_MODEL, "input_type": input_type, "output_dtype": config.QUERY_DTYPE,
            "dimensions": len(vec), "vector": vec, "sha256": embedding_sha256(vec)}


def add_embedding(task: Task, *, run_id: str) -> dict:
    """Embed an existing stored query without touching its narrative (hash re-verified)."""
    q = load_query(task)
    q["embedding"] = embed_query(q["narrative"], run_id=run_id)
    path = task.root / QUERY_FILE
    path.write_text(json.dumps(q, indent=1) + "\n")
    return load_query(task)


def make_query(task: Task, *, run_id: str) -> dict:
    """One narrator call on the seed; the same prompt as memory narratives, fix not known."""
    runner = LocalRunner()
    ws = runner.prepare(task)
    try:
        base = runner.run(ws, task.diag_cmd, 120)
        pinned = pin_focal(ws, base)
    finally:
        runner.cleanup(ws)
    seed = {p: (task.repo / p).read_text() for p in task.allowlist}
    symbols = task_symbols(pinned.function, base)
    narrative, violations, cost = narrate_task(
        seed, base, pinned.function, None, forbidden_tokens(task.repo, task.allowlist, symbols),
        run_id=run_id, phase="dev", attempt_n=0)
    return {"task_id": task.task_id, "narrative": narrative, "error_symbols": symbols,
            "query_sha256": query_sha256(narrative, symbols),
            "embedding": embed_query(narrative, run_id=run_id),
            "focal": pinned.as_doc(), "narrative_violations": violations,
            "narrator_model": os.environ.get("CODING_MODEL"),
            "narrator_prompt_sha256": hashlib.sha256(NARRATOR_SYSTEM.encode()).hexdigest(),
            "cost_usd": round(cost, 6), "created_at": datetime.now(timezone.utc).isoformat()}
