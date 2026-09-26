import dataclasses
import json
import os
import shutil

import pytest

from reflex_harness import agent, config, controller, narrator
from reflex_harness.queries import QUERY_FILE, QueryError, load_query, query_sha256
from reflex_harness.runner import load_task

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
        self.results, self._distinct = list(results or []), distinct or []

    def aggregate(self, pipeline):
        return iter(self.results.pop(0))

    def distinct(self, *a, **k):
        return self._distinct


def test_memory_selection_uses_the_stored_query_and_never_the_narrator(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("no narrator or model call at selection time")
    monkeypatch.setattr(narrator, "narrate_task", forbidden)
    monkeypatch.setattr(agent, "call", forbidden)
    monkeypatch.setattr(controller, "_log_embed", lambda *a, **k: None)
    monkeypatch.setattr(controller, "lexical_match_count", lambda *a, **k: 0)
    retrieved = [{"checkpoint_id": "c1", "family": "semantic_repetition",
                  "fusion": {"value": 0.0164, "details": []}},
                 {"checkpoint_id": "c2", "family": "oscillation", "fusion": {"value": 0.0161, "details": []}}]
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


@pytest.mark.skipif(not os.environ.get("MONGODB_URI"), reason="needs Atlas")
def test_two_runs_retrieve_identical_top_k_from_the_fixed_query():
    from reflex_harness.pipelines import retrieval_pipeline
    from reflex_harness.store import db
    q = load_query(TASK)
    runs = [list(db()["checkpoints"].aggregate(retrieval_pipeline(
        q["narrative"], q["error_symbols"], config.SNAPSHOT_ID, config.PROTOCOL))) for _ in range(2)]
    assert load_query(TASK)["query_sha256"] == q["query_sha256"]
    assert [r["checkpoint_id"] for r in runs[0]] == [r["checkpoint_id"] for r in runs[1]]
    # scores: equal up to Automated Embedding's per-call query-embedding noise (measured <= 2e-4)
    for a, b in zip(*runs):
        sa = next(d["value"] for d in a["fusion"]["details"] if d["inputPipelineName"] == "semantic")
        sb = next(d["value"] for d in b["fusion"]["details"] if d["inputPipelineName"] == "semantic")
        assert abs(sa - sb) < 1e-3


def _memory_row(monkeypatch, lexical_count):
    monkeypatch.setattr(controller, "_log_embed", lambda *a, **k: None)
    monkeypatch.setattr(controller, "lexical_match_count", lambda *a, **k: lexical_count)

    def doc(cid, fam, fusion, sem):
        return {"checkpoint_id": cid, "family": fam, "fusion": {"value": fusion, "details": [
            {"inputPipelineName": "lexical", "rank": 0, "weight": 1.0},
            {"inputPipelineName": "semantic", "rank": 1 if sem > 0.78 else 2, "weight": 1.0, "value": sem}]}}
    retrieved = [doc("c1", "semantic_repetition", 0.0164, 0.80), doc("c2", "oscillation", 0.0161, 0.77)]
    fake = {"attempts": _Coll(distinct=["focused"]),
            "checkpoints": _Coll(results=[retrieved, [{"_id": "dependency", "score": 0.5}]])}
    monkeypatch.setattr(controller, "db", lambda: fake)
    return controller.select_next("memory", task=TASK, run_id="r", phase="dev", attempt_n=1,
                                  trigger="regression", configs={c["config_id"]: c for c in config.CONFIGS_R1},
                                  snapshot="mem-v1", registry="r1", protocol="p1")


def test_retrieval_diagnostics_logged_with_gate8_margin_definition(monkeypatch):
    row = _memory_row(monkeypatch, lexical_count=0)
    r = row["retrieval"]
    assert r["query_sha256"] == load_query(TASK)["query_sha256"]
    assert abs(r["semantic_margin"] - (0.80 - 0.77)) < 1e-12 and r["lexical_matches"] == 0
    assert [(t["rank"], t["family"], t["semantic_score"], t["lexical_rank"]) for t in row["retrieved"]] == \
        [(1, "semantic_repetition", 0.80, 0), (2, "oscillation", 0.77, 0)]
    log = controller.selection_log("memory", "semantic_repetition", "solved", 1, [], row, 2)
    assert log["semantic_margin"] == r["semantic_margin"] and log["query_sha256"] == r["query_sha256"]
    assert [n["semantic_score"] for n in log["neighbours"]] == [0.80, 0.77]


def test_lexical_diagnostic_never_changes_the_choice(monkeypatch):
    assert _memory_row(monkeypatch, 0)["chosen_config_id"] == _memory_row(monkeypatch, 7)["chosen_config_id"]
