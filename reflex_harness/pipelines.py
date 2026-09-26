"""Aggregation pipelines. Pure functions: parameters in, pipeline list out (SPEC §9.4-9.5)."""
from . import config

NEIGHBORHOOD = 2  # top-k checkpoints, chosen before excluding tried configs


def _rank_fusion(narrative, symbols, snapshot_id, protocol):
    """Hybrid retrieval over checkpoints: autoEmbed on failure_narrative + lexical on error_symbols."""
    return {"$rankFusion": {
        "input": {"pipelines": {
            "semantic": [{"$vectorSearch": {
                "index": config.VECTOR_INDEX, "path": "failure_narrative",
                "query": narrative, "numCandidates": 40, "limit": 4,
                "filter": {"snapshot_id": snapshot_id, "compat.protocol": protocol}}}],
            "lexical": [
                {"$search": {"index": config.TEXT_INDEX, "compound": {
                    "must": [{"text": {"query": symbols, "path": "error_symbols"}}],
                    "filter": [{"equals": {"path": "snapshot_id", "value": snapshot_id}},
                               {"equals": {"path": "compat.protocol", "value": protocol}}]}}},
                {"$limit": 4}]}},
        "combination": {"weights": {"semantic": 1, "lexical": 1}},
        "scoreDetails": True}}


def retrieval_pipeline(narrative, symbols, snapshot_id, protocol):
    """The retrieval half of selection_pipeline: the neighborhood with fusion score details."""
    return [
        _rank_fusion(narrative, symbols, snapshot_id, protocol),
        {"$limit": NEIGHBORHOOD},
        {"$project": {"_id": 0, "checkpoint_id": 1, "family": 1, "task_id": 1,
                      "failure_narrative": 1, "error_symbols": 1, "outcomes": 1,
                      "fusion": {"$meta": "scoreDetails"}}},
    ]


def selection_pipeline(narrative, symbols, snapshot_id, protocol, registry, tried):
    """Retrieve the neighborhood and rank every untried config; row 0 is the choice.

    A solve counts only if the trial passed diagnostics AND protected tests.
    Sort: score desc -> nearest_solve_rank asc (on a score tie, the config solved by the
    nearest neighbour wins) -> mean_cost asc (only when rank can't decide) -> order asc.
    Empty result = configurations exhausted.
    """
    tried = list(tried)
    return [
        _rank_fusion(narrative, symbols, snapshot_id, protocol),
        {"$limit": NEIGHBORHOOD},
        {"$project": {"checkpoint_id": 1, "fusion": {"$meta": "scoreDetails"},
                      "outcomes": {"$filter": {"input": "$outcomes",
                                               "cond": {"$not": {"$in": ["$$this.config_id", tried]}}}}}},
        {"$setWindowFields": {"sortBy": {"fusion.value": -1},        # 1 = nearest neighbour
                              "output": {"rank": {"$documentNumber": {}}}}},
        {"$unwind": "$outcomes"},
        {"$group": {"_id": "$outcomes.config_id", "support": {"$sum": 1},
                    "solves": {"$sum": {"$cond": [
                        {"$and": ["$outcomes.solved", "$outcomes.verified"]}, 1, 0]}},
                    "regressions": {"$sum": {"$cond": ["$outcomes.regression", 1, 0]}},
                    "mean_cost": {"$avg": "$outcomes.cost_usd"},
                    "nearest_solve_rank": {"$min": {"$cond": [
                        {"$and": ["$outcomes.solved", "$outcomes.verified"]}, "$rank", 99]}},
                    "evidence": {"$push": "$checkpoint_id"}}},
        {"$unionWith": {"coll": "configs", "pipeline": [
            {"$match": {"registry": registry, "config_id": {"$nin": tried}}},
            {"$project": {"_id": "$config_id", "support": {"$literal": 0},
                          "solves": {"$literal": 0}, "regressions": {"$literal": 0},
                          "mean_cost": {"$literal": 1e9}, "nearest_solve_rank": {"$literal": 99},
                          "order": 1}}]}},
        {"$group": {"_id": "$_id", "support": {"$max": "$support"},
                    "solves": {"$max": "$solves"}, "regressions": {"$max": "$regressions"},
                    "mean_cost": {"$min": "$mean_cost"}, "order": {"$max": "$order"},
                    "nearest_solve_rank": {"$min": "$nearest_solve_rank"},
                    "evidence": {"$first": "$evidence"}}},
        {"$addFields": {"score": {"$divide": [
            {"$subtract": ["$solves", {"$multiply": [2, "$regressions"]}]},
            {"$add": ["$support", 1]}]}}},
        {"$sort": {"score": -1, "nearest_solve_rank": 1, "mean_cost": 1, "order": 1}},
    ]
