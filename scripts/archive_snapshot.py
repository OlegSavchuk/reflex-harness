"""Move a snapshot's checkpoints out of `checkpoints` into `checkpoints_archive`, labelled.
With --copy, archive a copy and leave `checkpoints` untouched (a frozen snapshot that must stay
retrievable, e.g. mem-v1 for reproducing Gate 8).

Retrieval searches only `checkpoints`, so archived evidence can never be retrieved.
--status invalid     evidence is wrong (e.g. built with weak tests)
--status superseded  evidence was valid; replaced by a rebuild with changed retrieval fields
Usage: python scripts/archive_snapshot.py --snapshot mem-v1 --status superseded --reason "..." [--copy]
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
ap.add_argument("--status", choices=("invalid", "superseded"), required=True)
ap.add_argument("--copy", action="store_true", help="archive a copy; do not remove from checkpoints")
args = ap.parse_args()
docs = list(db()["checkpoints"].find({"snapshot_id": args.snapshot}))
if not docs:
    sys.exit(f"no checkpoints in {args.snapshot}")
now = datetime.now(timezone.utc)
for d in docs:
    d["archived_from_id"] = d.pop("_id")
    d.update(archive_status=args.status, invalid=args.status == "invalid",
             archive_reason=args.reason, archived_at=now, archived_as_copy=args.copy)
db()["checkpoints_archive"].insert_many(docs)
n = 0 if args.copy else db()["checkpoints"].delete_many({"snapshot_id": args.snapshot}).deleted_count
print(f"archived {len(docs)} checkpoints of {args.snapshot} as {args.status.upper()}; removed {n} from checkpoints"
      f"{' (copy: checkpoints untouched)' if args.copy else ''}")
for status in ("invalid", "superseded"):
    q = {"invalid": True} if status == "invalid" else {"archive_status": "superseded"}
    print(f"  checkpoints_archive {status}: {db()['checkpoints_archive'].count_documents(q)}")
