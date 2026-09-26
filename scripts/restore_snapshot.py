"""Restore an archived snapshot into `checkpoints` and assert its content hash.

Usage: python scripts/restore_snapshot.py --snapshot mem-v1 --hash <sha256>
Archived docs are selected by snapshot_id + the hash recorded in their archive_reason.
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reflex_harness.store import db  # noqa: E402
from snapshot_hash import snapshot_hash  # noqa: E402

ARCHIVE_FIELDS = ("archived_from_id", "archive_status", "invalid", "archive_reason", "archived_at",
                  "invalid_reason", "restored_at")

ap = argparse.ArgumentParser()
ap.add_argument("--snapshot", required=True)
ap.add_argument("--hash", required=True)
args = ap.parse_args()
if db()["checkpoints"].count_documents({"snapshot_id": args.snapshot}):
    sys.exit(f"{args.snapshot} is live in checkpoints; archive it first")
docs = list(db()["checkpoints_archive"].find({"snapshot_id": args.snapshot,
                                               "archive_reason": {"$regex": args.hash}}))
if not docs:
    sys.exit("no archived docs match")
restored = []
for d in docs:
    doc = {k: v for k, v in d.items() if k not in ARCHIVE_FIELDS and k != "_id"}
    doc["_id"] = d["archived_from_id"]
    restored.append(doc)
db()["checkpoints"].insert_many(restored)
h, n = snapshot_hash(args.snapshot)
if h != args.hash:
    db()["checkpoints"].delete_many({"_id": {"$in": [d["_id"] for d in restored]}})
    sys.exit(f"hash mismatch after restore: {h} != {args.hash}; rolled back")
db()["checkpoints_archive"].update_many({"_id": {"$in": [d["_id"] for d in docs]}},
                                        {"$set": {"restored_at": datetime.now(timezone.utc)}})
print(f"restored {n} checkpoints of {args.snapshot}; content hash verified {h}")
