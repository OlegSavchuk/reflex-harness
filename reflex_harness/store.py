"""pymongo client and database handle. One client per process."""
from datetime import datetime, timezone
from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

from . import config


@lru_cache(maxsize=1)
def client() -> MongoClient:
    if not config.MONGODB_URI:
        raise RuntimeError("MONGODB_URI is not set")
    # Driver defaults for pool/timeouts: single-process CLI, low concurrency.
    return MongoClient(config.MONGODB_URI, appname="reflex-harness", tz_aware=True)


def db() -> Database:
    return client()[config.MONGODB_DB]


def log_call(*, run_id: str, phase: str, attempt_n: int, component: str, model: str,
             input_tokens: int, output_tokens: int, cost_usd: float, latency_ms: int,
             **extra) -> None:
    """One `calls` row per external call, including failed calls. No exceptions."""
    db()["calls"].insert_one({
        "run_id": run_id, "phase": phase, "attempt_n": attempt_n, "component": component,
        "model": model, "input_tokens": input_tokens, "output_tokens": output_tokens,
        "cost_usd": cost_usd, "latency_ms": latency_ms, **extra,
        "created_at": datetime.now(timezone.utc)})
