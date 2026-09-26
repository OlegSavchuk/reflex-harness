# reflex-harness

A coding-agent harness that detects repeated failed fixes and changes the agent's
context using evidence stored in MongoDB Atlas. Python 3.10+.

**Read `docs/SPEC.md` first** — full build specification: architecture, decision ladder,
selection pipeline, Jev contract, task suite, evaluation protocol, build gates.

## Rules for any assistant working here

- Never read, print, or commit `.env`. Credentials come from environment variables only.
- Never hard-code `tried_config_ids`, `snapshot_id`, or thresholds into a pipeline.
  They are function parameters.
- Protected evaluation tests live outside every agent workspace. Never copy them in.
- The frozen memory snapshot is read-only during evaluation. Evaluation writes go to
  `attempts`, `decisions` and `calls` with `phase: "eval"`, never to `checkpoints`.
- Every external model call writes one row to `calls`. No exceptions.
- Workspaces are git worktrees (seed = the only commit); `git` must be on PATH. A strategy
  switch resets to the seed through `controller.switch_strategy` only, and asserts the tree
  hash. Never add a second reset path, and never continue after `DirtyTreeError`.
- Verification = protected tests + the static gaming-pattern check on the final diff
  (`runner.static_violations`: caller/stack inspection and test-context sniffing).
- Each task has a frozen query in `tasks/<id>/query.json` (narrative + error_symbols + sha256, and
  its int8 voyage-4 embedding + sha256), made once by `scripts/make_queries.py`. Retrieval uses the
  stored vector as `queryVector`; never call the narrator or an embedding API at eval time.
- Suite runs (`scripts/run_suite.py`) generate attempt 1 once per task and replay it in every
  arm; never give arms independently sampled first attempts.
- A narrator-only change (prompt, symbol construction) re-narrates the frozen snapshot with
  `scripts/renarrate_snapshot.py`; never rebuild memory (that re-samples the evidence).
  Archive, don't delete: `scripts/archive_snapshot.py --status invalid|superseded`. Run `scripts/validate_tasks.py` and `scripts/audit_gaming.py`
  after any change to a task.
- Use the MongoDB skills in `.claude/skills/` for query writing, search/vector
  indexes, schema questions and connection setup. The MCP server is read-only;
  create indexes through `scripts/`, not through MCP, so setup is reproducible.

## Output format for MongoDB code

- Driver: `pymongo` (sync). Pipelines are Python lists of dicts.
- Aggregation pipelines live in `reflex_harness/pipelines.py` as functions that take
  parameters and return the pipeline list. No string templating.
- Datetimes are timezone-aware UTC (`datetime.now(timezone.utc)`). Models don't
  know today's date — run `date -u` if a query depends on it.

## Cluster facts

- Atlas Hackathon Sandbox, M10, MongoDB 8.0.x, AWS single region.
- Available: `$vectorSearch`, `$search`, `$rankFusion`, change streams, `$unionWith`.
  Reflex retrieval is **semantic-only**: one `$vectorSearch` stage (no `$search`/`$rankFusion`).
- NOT available on 8.0: `$scoreFusion` (8.2+), `$rerank` (8.3). Do not use them.
- Automated Embedding (`autoEmbed`) is a Preview feature; requires storage
  auto-scaling. Embeddings are generated asynchronously — poll until searchable.
- `$vectorSearch` and `$search` must be the first stage of their pipeline.
  Filter inside the stage (`filter` / compound `filter`), not with `$match` before it.

## Database: `reflex`

### Collection: `configs` — versioned registry of the four context configurations

```python
class Config(TypedDict):
    config_id: str            # "focused" | "caller" | "dependency" | "diagnostic"
    registry: str             # registry version, e.g. "r1"; selection filters on it
    order: int                # fixed exploration / tie-break order, 1..4
    context: dict             # {"focal": bool, "error": bool, "callers": bool, "deps": bool}
    workflow: dict            # {"diagnostic_first": bool}
```
Example:
```json
{"config_id": "caller", "registry": "r1", "order": 2,
 "context": {"focal": true, "error": true, "callers": true, "deps": false},
 "workflow": {"diagnostic_first": false}}
```
Indexes: unique `{registry: 1, config_id: 1}`.

### Collection: `checkpoints` — frozen development memory; the ONLY collection retrieval searches

```python
class Outcome(TypedDict):
    config_id: str
    solved: bool              # all diagnostic tests passed after the one trial attempt
    verified: bool            # protected tests also passed (dev tasks only). A solve = solved AND verified
    regression: bool          # a previously passing diagnostic test failed
    cost_usd: float           # total model cost of the trial

class Checkpoint(TypedDict):
    checkpoint_id: str
    snapshot_id: str          # frozen memory version, e.g. "mem-v1"
    family: str               # "oscillation" | "semantic_repetition"
    task_id: str              # dev task that produced it (never an eval task)
    failure_narrative: str    # 2-3 sentences from the TASK (seed code, seed failing tests, verified fix
                              # diff), never the agent's edits. Structural only: no identifiers, paths,
                              # domain nouns or test names. autoEmbed field.
    error_symbols: str        # from the seed baseline: focal name, failing test names, exception types.
    root_cause_from: str | None  # config whose verified fix the narrative's cause sentence describes
    focal: dict               # pinned focal the context was built around: {"path", "function", "source"}
    facets: dict              # {"callers_of_focal": int, "files_touched": int}
    compat: dict              # {"language": "python", "protocol": "p1", "registry": "r1"}
    prior_attempts: list      # identical attempt summaries shown to all four trials
    outcomes: list[Outcome]   # exactly one per config, both successes and failures
    narrative_violations: list # validator violations left after the narrator's one retry ([] = valid)
    build_cost_usd: float     # narrator + four trials
    created_at: datetime
```
Example (truncated):
```json
{"checkpoint_id": "osc-dev-01", "snapshot_id": "mem-v1", "family": "oscillation",
 "failure_narrative": "Changing a shared helper to satisfy one caller broke a second caller that passes values in a different unit. The agent reverted, restoring the original failure.",
 "error_symbols": "apply_tax test_invoice_total_cents test_refund_total_keeps_cents TypeError AssertionError",
 "compat": {"language": "python", "protocol": "p1", "registry": "r1"},
 "outcomes": [{"config_id": "focused", "solved": false, "verified": false, "regression": true, "cost_usd": 0.021},
              {"config_id": "caller", "solved": true, "verified": true, "regression": false, "cost_usd": 0.034}]}
```
Indexes:
- Vector search `ckpt_vec`:
  `{"fields": [{"type": "autoEmbed", "modality": "text", "path": "failure_narrative", "model": "voyage-4"},
  {"type": "filter", "path": "snapshot_id"}, {"type": "filter", "path": "compat.protocol"}]}`
- (Atlas Search `ckpt_text` on `error_symbols` was Gate 8's lexical branch; removed in Gate 9 P1 —
  retrieval is semantic-only.)
- Regular: unique `{checkpoint_id: 1}`.

Query form for autoEmbed (verify at gate 1): `$vectorSearch` with `query: "<text>"`
instead of `queryVector`. Fallback if it fails: manual Voyage embeddings + `queryVector`, disclosed.

### Collection: `attempts` — exact record of every attempt, every run

```python
class Attempt(TypedDict):
    run_id: str
    phase: str                # "dev" | "eval"
    mode: str                 # "memory" | "fallback" | "plain_retry" | "build" (memory building)
    task_id: str
    attempt_n: int            # 1-based
    config_id: str
    focal_source: str         # "traceback" | "manifest" | "re-resolved" — how the pinned focal was
                              # resolved (disclosed). Pinned once per task from the seed baseline.
    parent_state_hash: str    # hash of allowlisted files before the patch
    state_hash: str           # after the patch
    patch: dict               # {"files": [{"path": str, "content": str}]}
    patch_fingerprint: str
    failed_tests: list[str]
    passed_tests: list[str]
    diag_pass: bool
    regression: bool
    rolled_back: bool         # controller restored parent state
    trigger: str | None       # None | "regression" | "exact_repeat" | "same_strategy"
    jev_p_repeating: float | None  # None: Jev replaced by the same_strategy rule at Gate 5 (SPEC §10)
    verified: bool            # protected tests passed (only meaningful when diag_pass)
    cost_usd: float           # model cost of this attempt (both calls for diagnostic)
    error: str | None         # unparseable reply / rejected patch / infra
    prompt: str               # user message of the patch call, as the model saw it
    created_at: datetime
```
Indexes: `{run_id: 1, attempt_n: 1}`, `{task_id: 1, phase: 1}`.

### Collection: `decisions` — one row per intervention

`run_id`, `task_id`, `attempt_n`, `trigger`, `tried_config_ids` (list),
`retrieved` (list of `{rank, checkpoint_id, family, semantic_score}`), `candidates` (the full sorted
table the selection pipeline returns: per-config support/solves/regressions/mean_cost/score),
`chosen_config_id` (row 0),
`reset` (`{from_config, to_config, seed_hash, tree_hash, seed_hash_verified}` on every switch),
`status` ("selected" | "insufficient_evidence" | "configurations_exhausted"), `policy`
("memory" | "fallback"), and for memory: `narrative`, `narrative_violations`, `error_symbols`;
`retrieved` entries also carry `family` and `failure_narrative` for the dashboard. `created_at`.

### Collection: `runs` — one row per task × arm run

`run_id`, `phase`, `arm`, `task_id`, `family`, `stop_reason` (SPEC §6.2, incl. `reset_failed`),
`verified_fix` (stop_reason == "solved"), `attempts`, `switched`, `configs_used`, `cost_usd`,
`input_tokens`, `output_tokens` (sums of the run's `calls` rows, abandoned attempts included),
`shared_attempt` (`{run_id, cost_usd}` of the attempt 1 replayed in every arm; its cost is
included in `cost_usd`), `snapshot_id` (memory arm), and the Gate 8 fields (SPEC §13.4):
`switch_attempt`, `triggers`, `neighbours` (top-1/top-2 `{rank, checkpoint_id, family,
semantic_score}`, memory arm only), `semantic_margin`, `query_sha256`, `random_seed`, `repeat`,
`chosen_config`, `designed_config`, `chosen_matches_designed`,
`pre_selection_end`; `created_at`.

### Collection: `calls` — cost ledger, one row per external call

`run_id`, `phase`, `attempt_n`, `component` ("agent" | "narrator" | "jev" | "embed"),
`model` (dated snapshot from the response), `input_tokens`, `output_tokens`,
`cost_usd`, `latency_ms`, `created_at`.
Index: `{run_id: 1, component: 1}`.

### Collection: `tasks` — bug-task registry

`task_id`, `family`, `split` ("dev" | "eval"), `repo_path`, `allowlist` (editable
source files), `diag_cmd`, `protected_cmd`. Reference fixes are never stored here.

## Selection policy (frozen)

score = (solves − 2 × regressions) / (support + 1), where a solve = `solved AND verified`
(diagnostics and protected tests both passed in the dev trial).
Sort: score desc → nearest_solve_rank asc (on a tie, the config verified-solved by the nearest
neighbour wins) → mean_cost asc (only when rank can't decide) → order asc. The pipeline returns
every untried config in that order; Python takes row 0 and stores the whole table in
`decisions.candidates`. Unknown configs get
`mean_cost = 1e9` (null would sort first). One configuration switch per task.
