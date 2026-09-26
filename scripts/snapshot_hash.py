"""Content hash of a memory snapshot: sha256 of canonical JSON of its checkpoints (minus _id).

Usage: python scripts/snapshot_hash.py [--snapshot mem-v1]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reflex_harness import config  # noqa: E402
from reflex_harness.store import db  # noqa: E402


def snapshot_hash(snapshot: str) -> tuple[str, int]:
    docs = list(db()["checkpoints"].find({"snapshot_id": snapshot}, {"_id": 0}).sort("checkpoint_id", 1))
    blob = json.dumps(docs, sort_keys=True, default=lambda v: v.isoformat() if hasattr(v, "isoformat") else str(v))
    return hashlib.sha256(blob.encode()).hexdigest(), len(docs)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=config.SNAPSHOT_ID)
    h, n = snapshot_hash(ap.parse_args().snapshot)
    print(f"{h}  ({n} checkpoints)")
