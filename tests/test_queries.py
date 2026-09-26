import dataclasses
import json
import os
import shutil

import pytest

from reflex_harness import agent, config, controller, narrator
from reflex_harness.queries import QUERY_FILE, QueryError, load_query, query_sha256
from reflex_harness.runner import load_task, task_ids

TASK = load_task("sem-eval-01")


def test_stored_query_is_byte_identical_across_loads_and_hash_verified():
    raw1 = (TASK.root / QUERY_FILE).read_bytes()
    q1, q2 = load_query(TASK), load_query(TASK)
    assert (TASK.root / QUERY_FILE).read_bytes() == raw1
    assert q1 == q2 and q1["query_sha256"] == query_sha256(q1["narrative"], q1["error_symbols"])


def test_tampered_or_missing_query_stops(tmp_path):
    root = tmp_path / "task"
    shutil.copytree(TASK.root, root, ignore=shutil.ignore_patterns("repo", "protected"))
    task = dataclasses.replace(TASK, root=root)
    q = json.loads((root / QUERY_FILE).read_text())
    q["narrative"] += " edited"
    (root / QUERY_FILE).write_text(json.dumps(q))
    with pytest.raises(QueryError):
        load_query(task)
    (root / QUERY_FILE).unlink()
    with pytest.raises(QueryError):
        load_query(task)


class _Coll:
    def __init__(self, results=None, distinct=None):
        self.results, self._distinct, self.pipelines = list(results or []), distinct or [], []

    def aggregate(self, pipeline):
        self.pipelines.append(pipeline)
        return iter(self.results.pop(0))

    def distinct(self, *a, **k):
        return self._distinct


def test_memory_selection_uses_the_stored_query_and_never_the_narrator(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("no narrator or model call at selection time")
    monkeypatch.setattr(narrator, "narrate_task", forbidden)
    monkeypatch.setattr(agent, "call", forbidden)
    retrieved = [{"checkpoint_id": "c1", "family": "semantic_repetition", "semantic_score": 0.80},
                 {"checkpoint_id": "c2", "family": "oscillation", "semantic_score": 0.77}]
    selected = [{"_id": "dependency", "score": 0.5}]
    fake = {"attempts": _Coll(distinct=["focused"]), "checkpoints": _Coll(results=[retrieved, selected])}
    monkeypatch.setattr(controller, "db", lambda: fake)
    configs = {c["config_id"]: c for c in config.CONFIGS_R1}
    row = controller.select_next("memory", task=TASK, run_id="r", phase="dev", attempt_n=1,
                                 trigger="regression", configs=configs, snapshot="mem-v1",
                                 registry="r1", protocol="p1")
    q = load_query(TASK)
    assert row["narrative"] == q["narrative"] and row["query_sha256"] == q["query_sha256"]
    assert row["chosen_config_id"] == "dependency"
    from bson.binary import Binary, BinaryVectorDtype
    for pipeline in fake["checkpoints"].pipelines:        # stored int8 vector, never text
        vs = pipeline[0]["$vectorSearch"]
        assert "query" not in vs and isinstance(vs["queryVector"], Binary)
        assert vs["queryVector"].as_vector().dtype == BinaryVectorDtype.INT8
        assert list(vs["queryVector"].as_vector().data) == q["embedding"]["vector"]


def test_tampered_embedding_stops(tmp_path):
    root = tmp_path / "task"
    shutil.copytree(TASK.root, root, ignore=shutil.ignore_patterns("repo", "protected"))
    task = dataclasses.replace(TASK, root=root)
    q = json.loads((root / QUERY_FILE).read_text())
    q["embedding"]["vector"][0] += 1
    (root / QUERY_FILE).write_text(json.dumps(q))
    with pytest.raises(QueryError):
        load_query(task)


@pytest.mark.skipif(not os.environ.get("MONGODB_URI"), reason="needs Atlas")
def test_stored_embedding_matches_the_memory_index():
    from reflex_harness.pipelines import retrieval_pipeline
    from reflex_harness.queries import query_input
    from reflex_harness.store import db
    q = load_query(TASK)
    emb = q["embedding"]
    index = next(i for i in db()["checkpoints"].list_search_indexes() if i["name"] == config.VECTOR_INDEX)
    auto = next(f for f in index["latestDefinition"]["fields"] if f["type"] == "autoEmbed")
    assert (emb["model"], emb["input_type"], emb["output_dtype"]) == (auto["model"], "query", "int8")
    assert emb["dimensions"] == len(emb["vector"]) == config.EMBED_DIMS
    by_vec = list(db()["checkpoints"].aggregate(retrieval_pipeline(query_input(q), config.SNAPSHOT_ID, config.PROTOCOL)))
    by_text = list(db()["checkpoints"].aggregate(retrieval_pipeline(q["narrative"], config.SNAPSHOT_ID, config.PROTOCOL)))
    assert [r["checkpoint_id"] for r in by_vec] == [r["checkpoint_id"] for r in by_text]
    for a, b in zip(by_vec, by_text):   # text path re-embeds per call (noise <= ~5e-4)
        assert abs(a["semantic_score"] - b["semantic_score"]) < 1e-3


def test_every_stored_query_is_in_the_memory_embedding_space():
    """All active tasks: voyage-4 query embeddings, int8, EMBED_DIMS values in [-128, 127]."""
    ids = task_ids()
    assert len(ids) >= 32
    for tid in ids:
        emb = load_query(load_task(tid))["embedding"]          # hash-verified
        assert (emb["model"], emb["input_type"], emb["output_dtype"]) == (config.EMBED_MODEL, "query", config.QUERY_DTYPE)
        assert emb["dimensions"] == len(emb["vector"]) == config.EMBED_DIMS, tid
        assert all(isinstance(x, int) and -128 <= x <= 127 for x in emb["vector"]), tid


@pytest.mark.skipif(not os.environ.get("MONGODB_URI"), reason="needs Atlas")
def test_memory_vectors_are_int8_in_the_stored_query_space():
    """Memory side: the index embeds with the stored queries' model, and Automated Embedding's
    stored vector for every checkpoint of the snapshot is int8 with EMBED_DIMS values (read from
    its internal materialized view). scripts/check_embedding_space.py additionally shows a Voyage
    document embedding reproduces each stored vector byte for byte."""
    from bson.binary import BinaryVectorDtype

    from reflex_harness.store import client, db
    index = next(i for i in db()["checkpoints"].list_search_indexes() if i["name"] == config.VECTOR_INDEX)
    auto = next(f for f in index["latestDefinition"]["fields"] if f["type"] == "autoEmbed")
    assert auto["model"] == config.EMBED_MODEL == load_query(TASK)["embedding"]["model"]
    internal = client()["__mdb_internal_search"]
    lease = internal["auto_embedding_leases"].find_one({"collectionName": "checkpoints"})
    view = internal[lease["materializedViewCollectionMetadata"]["collectionName"]]
    ids = [d["_id"] for d in db()["checkpoints"].find({"snapshot_id": config.SNAPSHOT_ID}, {"_id": 1})]
    vecs = [d["_autoEmbed"]["failure_narrative"].as_vector() for d in view.find({"_id": {"$in": ids}})]
    assert ids and len(vecs) == len(ids)
    assert all(v.dtype == BinaryVectorDtype.INT8 and len(v.data) == config.EMBED_DIMS for v in vecs)


@pytest.mark.skipif(not os.environ.get("MONGODB_URI"), reason="needs Atlas")
def test_ten_repeated_retrievals_are_byte_identical():
    from reflex_harness.pipelines import retrieval_pipeline
    from reflex_harness.queries import query_input
    from reflex_harness.store import db
    q = load_query(TASK)
    runs = [[(r["checkpoint_id"], r["semantic_score"]) for r in db()["checkpoints"].aggregate(
        retrieval_pipeline(query_input(q), config.SNAPSHOT_ID, config.PROTOCOL))] for _ in range(10)]
    assert all(r == runs[0] for r in runs) and len(runs[0]) == 2


def test_retrieval_diagnostics_logged_with_gate8_margin_definition(monkeypatch):
    retrieved = [{"checkpoint_id": "c1", "family": "semantic_repetition", "semantic_score": 0.80},
                 {"checkpoint_id": "c2", "family": "oscillation", "semantic_score": 0.77}]
    fake = {"attempts": _Coll(distinct=["focused"]),
            "checkpoints": _Coll(results=[retrieved, [{"_id": "dependency", "score": 0.5}]])}
    monkeypatch.setattr(controller, "db", lambda: fake)
    row = controller.select_next("memory", task=TASK, run_id="r", phase="dev", attempt_n=1,
                                 trigger="regression", configs={c["config_id"]: c for c in config.CONFIGS_R1},
                                 snapshot="mem-v1", registry="r1", protocol="p1")
    r = row["retrieval"]
    assert r["query_sha256"] == load_query(TASK)["query_sha256"] and "lexical_matches" not in r
    assert abs(r["semantic_margin"] - (0.80 - 0.77)) < 1e-12
    assert [(t["rank"], t["family"], t["semantic_score"]) for t in row["retrieved"]] == \
        [(1, "semantic_repetition", 0.80), (2, "oscillation", 0.77)]
    log = controller.selection_log("memory", "semantic_repetition", "solved", 1, [], row, 2)
    assert log["semantic_margin"] == r["semantic_margin"] and log["query_sha256"] == r["query_sha256"]
    assert [n["semantic_score"] for n in log["neighbours"]] == [0.80, 0.77]
