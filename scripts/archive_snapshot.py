"""Move a snapshot's checkpoints out of `checkpoints` into `checkpoints_archive`, labelled.

Retrieval searches only `checkpoints`, so archived evidence can never be retrieved.
Usage: python scripts/archive_snapshot.py --snapshot mem-v1 --reason "..."
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reflex_harness.store import db  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--snapshot", required=True)
ap.add_argument("--reason", required=True)
args = ap.parse_args()
docs = list(db()["checkpoints"].find({"snapshot_id": args.snapshot}))
if not docs:
    sys.exit(f"no checkpoints in {args.snapshot}")
now = datetime.now(timezone.utc)
for d in docs:
    d["archived_from_id"] = d.pop("_id")
    d.update(invalid=True, invalid_reason=args.reason, archived_at=now)
db()["checkpoints_archive"].insert_many(docs)
n = db()["checkpoints"].delete_many({"snapshot_id": args.snapshot}).deleted_count
print(f"archived {len(docs)} checkpoints of {args.snapshot} as INVALID; removed {n} from checkpoints")
print(f"checkpoints_archive now holds {db()['checkpoints_archive'].count_documents({'invalid': True})} invalid docs")
