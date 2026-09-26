"""Confirm memory checkpoints and stored queries share one embedding space (Gate 9 P2b).

Memory side: the vector Automated Embedding stored for every checkpoint of the snapshot (read,
never written, from its internal materialized view) and the index definition's model. Query
side: every active task's stored query embedding. Checks: same model, same dimensions, int8 on
both sides; then one Voyage call per checkpoint narrative (voyage-4, input_type=document, int8)
must reproduce the vector Atlas stored, i.e. Atlas embeds and quantizes exactly as the stored
queries were. Writes results/phase2/embedding_space.json.

Usage: python scripts/check_embedding_space.py [--snapshot mem-v1]
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bson.binary import BinaryVectorDtype  # noqa: E402

from reflex_harness import config  # noqa: E402
from reflex_harness.queries import embed_query, load_query  # noqa: E402
from reflex_harness.runner import load_task, task_ids  # noqa: E402
from reflex_harness.store import client, db  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def memory_vectors(snapshot: str) -> dict:
    internal = client()["__mdb_internal_search"]
    lease = internal["auto_embedding_leases"].find_one({"collectionName": "checkpoints"})
    view = internal[lease["materializedViewCollectionMetadata"]["collectionName"]]
    ckpts = {d["_id"]: d for d in db()["checkpoints"].find({"snapshot_id": snapshot},
                                                           {"checkpoint_id": 1, "failure_narrative": 1})}
    out = {}
    for d in view.find({"_id": {"$in": list(ckpts)}}):
        v = d["_autoEmbed"]["failure_narrative"].as_vector()
        out[ckpts[d["_id"]]["checkpoint_id"]] = (ckpts[d["_id"]]["failure_narrative"], v)
    missing = sorted(c["checkpoint_id"] for i, c in ckpts.items() if c["checkpoint_id"] not in out)
    return out, missing


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b)) / math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=config.SNAPSHOT_ID)
    snapshot = ap.parse_args().snapshot
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    index = next(i for i in db()["checkpoints"].list_search_indexes() if i["name"] == config.VECTOR_INDEX)
    auto = next(f for f in index["latestDefinition"]["fields"] if f["type"] == "autoEmbed")
    mem, missing = memory_vectors(snapshot)
    queries = {t: load_query(load_task(t))["embedding"] for t in task_ids()}
    q_space = {(e["model"], e["input_type"], e["output_dtype"], e["dimensions"], len(e["vector"])) for e in queries.values()}
    m_space = {(v.dtype.name, len(v.data)) for _, v in mem.values()}
    checks = {
        "index model == config": auto["model"] == config.EMBED_MODEL,
        "every checkpoint has a stored vector": not missing,
        "memory vectors int8 x EMBED_DIMS": m_space == {("INT8", config.EMBED_DIMS)},
        "queries one space (model, query, int8, dims)": q_space == {(config.EMBED_MODEL, "query", "int8",
                                                                     config.EMBED_DIMS, config.EMBED_DIMS)},
        "query int8 values in [-128, 127]": all(isinstance(x, int) and -128 <= x <= 127
                                               for e in queries.values() for x in e["vector"]),
    }
    reproduced = []
    for cid, (text, v) in sorted(mem.items()):
        e = embed_query(text, run_id=f"embed-space-{cid}-{stamp}", input_type="document")
        reproduced.append({"checkpoint_id": cid, "identical": e["vector"] == list(v.data),
                           "cosine": round(cosine(e["vector"], v.data), 6),
                           "max_abs_diff": max(abs(a - b) for a, b in zip(e["vector"], v.data))})
    checks["Voyage document int8 reproduces Atlas vectors (cosine >= 0.999)"] = all(r["cosine"] >= 0.999 for r in reproduced)
    for name, ok in checks.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    for r in reproduced:
        print(f"        {r['checkpoint_id']:<24} identical={r['identical']} cosine={r['cosine']} max|diff|={r['max_abs_diff']}")
    print(f"  memory: {len(mem)} checkpoints ({snapshot}), index model {auto['model']}; queries: {len(queries)} tasks")
    out = ROOT / "results" / "phase2" / "embedding_space.json"
    out.write_text(json.dumps({"stamp": stamp, "snapshot": snapshot, "index_model": auto["model"],
                               "memory_space": sorted(m_space), "query_space": sorted(q_space),
                               "checks": checks, "reproduced": reproduced}, indent=1, default=list) + "\n")
    sys.exit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()
