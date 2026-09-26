# Reflex — Build Specification

> Single source of truth for what we are building today. Read this before writing code.
> `CLAUDE.md` holds the database schemas and coding rules; this file holds everything else.
> If this file and the code disagree, stop and ask — do not silently pick one.

---

## 1. One-line summary

**Reflex is a harness around a coding agent that notices when the agent is repeating a
failed fix, and changes the agent's working context using measured evidence of what
worked on similar failures, stored and selected inside MongoDB Atlas.**

Pitch (30s):

> Coding agents don't just fail — they fail in loops. Fix one bug, break another, fix that,
> bring the first one back. Reflex notices. Tests tell it what broke. Jev tells it when the
> agent is repeating an idea in a new diff. MongoDB tells it what worked the last time an
> agent was stuck like this — and Reflex changes the agent's working context before it
> spends another attempt. Every intervention is a recorded experiment. The memory is the
> accumulated result.

Pre-measurement claim (use until we have numbers):
"Reflex aims to turn repeated failed attempts into verified fixes within the same budget."

Post-measurement claim template:
"Across our frozen task suite, Reflex solved X of N versus Y of N, at Z cost per verified fix."

---

## 2. The problem

Ilya Sutskever described it: you ask a model to fix a bug, it introduces a second bug; you
point that out, it brings back the first. You can alternate indefinitely. Models score well
on evals and still burn real budget in these loops.

Reflex does **not** fix model generalization. It stops the agent from spending its budget
rediscovering that its current strategy doesn't work, and forces a strategy change backed
by evidence.

---

## 3. Event context (constraints that shape the design)

- Harness Engineering hackathon, Sept 26. Statement One: recursive harnessing — a harness
  that adapts its own environment (rules, context policies, tool access) to the task.
- MongoDB must be the data and memory layer, built in the **Atlas Hackathon Sandbox**.
  Removing MongoDB must break the project, not just slow it down.
- All work original. Public repo. 1-minute demo video. Submitted via Cerebral Valley.
- Forbidden category includes AI job-application screening. Reflex ranks **configurations
  and code fixes, never people.**

---

## 4. What Reflex is and is not

| Is | Is not |
|---|---|
| A controller that owns the attempt loop | A new coding model |
| Context-configuration selection from evidence | An LLM inventing new configs (out of scope) |
| Bug-fixing against a fixed test suite | Feature building ("add a button") — no test signal |
| One process: CLI + dashboard | A VS Code extension, an MCP tool, a skill |
| A wrapper today, a Claude Code stop-hook later | Something the agent chooses to call |

Why not an MCP tool: a stuck agent is confident. Tools are pull; intervention must be push.
Reflex has to interrupt from outside.

---

## 5. Components and responsibilities

| Component | Responsibility | Never does |
|---|---|---|
| **Coding model** (OpenRouter, pinned, e.g. `openai/gpt-6-luna-20260922`) | Writes a patch from the context Reflex gives it | Reads the repo itself, runs tests, decides pass/fail |
| **Test runner** (`pytest` + `pytest-json-report`, subprocess) | Produces facts: which tests pass/fail | Judges strategy |
| **Rules** (Python) | Regression, exact repeat, strict-subset progress, budget | Semantic judgment |
| **Jev** (`typesafe/jev-1.13` via OpenRouter Decisions API) | One judgment: "is this the same failed strategy in a new diff?" | Pass/fail, config choice |
| **MongoDB Atlas** | Stores every attempt; retrieves similar past failures; **selects the next config** in one aggregation | Nothing is decided in Python that the pipeline can decide |
| **Controller** (`reflex_harness/controller.py`) | Owns budget, loop, rollback, the one switch | Chooses configs by itself |
| **Dashboard** (FastAPI + change stream + SSE) | Shows the run live | Writes anything |

The architecture sentence: **rules know what happened on this task, MongoDB knows what
happened on every other task, Jev bridges the case neither can see — an attempt that is
semantically the last one wearing a different diff.**

---

## 6. The runtime loop

Budget per task: **3 patch attempts**, fixed token cap, 90–180s per attempt.
At most **one configuration switch per task**, from any trigger.

```
start task under config "focused"
loop:
  build prompt from active config            (context.py)
  model returns {"files":[{"path","content"}]} (agent.py)
  reject paths outside task allowlist
  apply to isolated workspace copy
  run diagnostic tests, parse JSON report    (runner.py)
  record attempt + calls                      (store.py)
  decision = decide(run, attempt)             (controller.py)
```

### 6.1 Decision ladder — ordered, cheapest and most certain first

After every attempt:

1. **Diagnostics pass?** → run protected final verification → stop (`solved` or `verification_failed`).
2. **Regression?** (any test that passed before now fails) → roll back to parent state,
   mark `rolled_back`, trigger = `regression`.
3. **Budget left?** No → stop (`budget_exhausted`, or `rolled_back_budget_exhausted` if 2 fired).
4. If a trigger fired and we already switched → stop (`intervention_limit_reached`).
5. If a trigger fired → **intervene**.
6. **Exact repeat?** Same state hash as an earlier attempt, or same patch fingerprint
   against the same parent state → trigger = `exact_repeat` → intervene (skip Jev).
7. **Progress that moved?** Failing set is a strict subset of the previous failing set (same
   suite, no missing/skipped tests) **and** the edit lies outside the focal region (same region
   as step 9) → continue without the same-strategy check. Real progress usually moves; a
   shrinking hack moved into a helper the agent just created does not count as moved.
   Shrinkage alone no longer short-circuits: a local hack in the same function can shrink the
   failing set (sem-dev-02: quarter-hour rounding took 3 failures to 1) while repeating the
   same strategy. That case goes to Jev with `shrank: true` in the packet.
   (3 failures → 2 *different* failures is not shrinkage.)
8. **Too early for Jev?** Already switched, or fewer than 2 completed attempts under the
   current config → continue.
9. **Same-strategy check (rule; replaced Jev at Gate 5).** Focal region = the pinned focal
   function + seed functions the failing tests call directly (by name or as a method; from the
   seed baseline) + any function the agent created during this run. Built once per run
   (`context.focal_region`). If both of the last two attempts' edits stay inside the region and
   failures remain → trigger = `same_strategy` → intervene. Else continue. Module-level lines
   of the focal file are ignored; module-level edits in other files are outside the region.
   (Smoke runs: the agent moved its hack into helpers it created, and also rewrote a seed
   sibling the failing tests call — both missed by the earlier "same focal function" rule.)
   (`controller.same_strategy`.) Jev was the plan here — packet with `failing_before`,
   `failing_after`, `shrank` — but it could not separate same-function shrinking hacks from
   genuine refinements (Gate 5, §10). Disclosed. A false positive costs one early switch to a
   config that still includes the focal, never lost context.

Controller-generated rollbacks are recorded separately and must never count as agent
oscillation. Log which trigger fired: "rules caught it" vs "Jev caught it" is evidence for
whether Jev earns its place.

### 6.2 Intervention

1. Build the query narrative with the same narrator prompt as dev memory (§9.3), from the task
   (seed code, seed failing tests); the fix is not known at this point.
2. Load `tried_config_ids` from **exact** current-task history (`attempts`), never from retrieval.
3. Select the next config: memory → the selection pipeline (§9.5); fallback → next untried
   config in registry order.
4. **Reset to seed (reset-on-switch).** One shared code path for every arm that switches
   (`controller.switch_strategy`): `git checkout -- .` and `git clean -fd` in the task
   worktree (each workspace is a git repo whose only commit is the seed), so edits *and* new
   files from the abandoned strategy are removed. Then compute the tree hash (sha256 over all
   files, independent of git) and assert it equals the seed hash recorded at `prepare`. On
   mismatch the run stops with `reset_failed` — never continue on a dirty tree.
5. Write one `decisions` row: selection evidence plus `reset: {from_config, to_config,
   seed_hash, tree_hash, seed_hash_verified}`. Load the config. `switched = True`,
   `attempts_in_config = 0`.
6. The new config's first prompt carries the line: *"The code has been reset to its original
   state. None of the edits described in the prior attempts below are present."* Prior-attempt
   summaries are still passed. Abandoned attempts still count toward the run's cost and tokens.
7. The new config gets at least one completed attempt before anything else can stop it,
   except diagnostics passing or budget exhaustion.

**Deliberate simplification.** Reset-on-switch isolates strategy selection: the new config
starts from clean code. We do not test recovery from a dirty tree. Evidence for the choice
(dev): without it, `dependency` on sem-dev-02 and `caller` on osc-dev-01 produced the correct
root-cause fix and still failed verification because edits from the abandoned `focused`
strategy (a rounding hack; a loosened type check) were left in place.

Stop reasons (store separately from `outcome`):
`solved`, `verification_failed`, `budget_exhausted`, `rolled_back_budget_exhausted`,
`intervention_limit_reached`, `configurations_exhausted`, `infrastructure_error`, `reset_failed`.

---

## 7. The four configurations

Same model, same budget. Only the information and workflow Reflex supplies change.
No task-specific hints ever.

| config_id | order | Agent receives |
|---|---|---|
| `focused` | 1 | Failing function + failing test output |
| `caller` | 2 | + every caller of the focal function in allowlisted files |
| `dependency` | 3 | + functions the focal function calls, dataclasses it touches |
| `diagnostic` | 4 | Focused context, but first writes a targeted check script; Reflex runs it and feeds output back; second call writes the patch. Both calls count toward cost. The script is saved in a scratch dir outside the workspace and run against a throwaway copy — never in the allowlist, never part of the patch or state hash |

### 7.1 Context resolution (`context.py`)

- **Focal pinning:** the focal is resolved **once per task**, from the seed's baseline failing
  run before attempt 1, and reused for every attempt, config and arm. Otherwise it drifts to
  downstream victims as edits change where things crash (Gate 3: `apply_tax` → `format_cents`),
  and a config would mean different things on different attempts — corrupting the evidence
  memory is built from. Pinning is harness bookkeeping, not a hint: every arm gets the same
  focal from the same seed. Re-resolved only if the pinned function no longer exists
  (`focal_source: "re-resolved"`). Each checkpoint stores its pinned `focal`.
- **Focal function:** fallback chain, source logged. (1) Deepest allowlisted frame in the
  failing tracebacks (most common across failing tests) → `focal_source: "traceback"`.
  (2) If no failing test has one (assertion-only failures), the `focal` field of the per-task
  `context_manifest.json` → `focal_source: "manifest"`. Every attempt records `focal_source`,
  so the disclosure is backed by data. Family B keeps its natural assertion-failure shape.
- **Traceback filter:** configs without callers/deps (`focused`, `diagnostic`) see, per failing
  test, only the test name, the first line of the error, and the focal-function frame.
  `caller` and `dependency` see the full traceback. Otherwise caller frames leak into
  `focused` and the configs are not really different. (The model may still guess from test
  names; calibration shows whether that happens.)
- **Files shown:** the full file of the focal function, plus full files of callers/dependencies
  when the config includes them (patches are full-file replacements).
- **Callers:** `ast` scan of allowlisted files for `Call` nodes to the focal name.
- **Dependencies:** `ast` walk of the focal function body for called names and annotated types.
- Fallback if `ast` resolution fights us: per-task manifest `context_manifest.json`
  (focal, and callers/deps if needed). **Disclose** if used.

### 7.2 Why the coding agent is a direct model call

If the agent could read the repo (Claude Code, Codex), "focused" vs "caller" would be
meaningless — it would open the caller itself. Reflex must assemble context; the model sees
only what Reflex hands it. This also gives uniform cost accounting.

---

## 8. Coding agent contract (`agent.py`)

- Endpoint: `POST https://openrouter.ai/api/v1/chat/completions`, `temperature: 0`,
  structured output requested, `usage: {"include": true}`.
- Output: `{"files": [{"path": "...", "content": "<full file>"}], "note": "<one line>"}`.
  **Full-file replacements, not diffs** — diffs fail to apply; our files are small.
- Reflex rejects any path not in the task allowlist. Tests are never in the allowlist.
- Prompt contains: goal, active context blocks, failing test output (truncated), and the
  prior attempt summaries for this task (what was changed, what happened). Never the
  protected tests. Never the reference fix.
- Record the dated model snapshot the response reports.

---

## 9. MongoDB design

Schemas, example documents and indexes: see `CLAUDE.md`. Database: `reflex`.
Collections: `tasks`, `configs`, `attempts`, `checkpoints`, `decisions`, `calls`.

### 9.1 Why each MongoDB feature is here

| Feature | Job | Why it's load-bearing |
|---|---|---|
| Automated Embedding (`autoEmbed`, voyage-4) | Embeds `failure_narrative` in-database, and embeds query text at query time | No embedding pipeline in our code |
| Atlas Search (`$search`) | Lexical match on `error_symbols` | Exact function/test names matter |
| `$rankFusion` | Fuses semantic + lexical rankings | Hybrid retrieval in one stage |
| `$unwind/$group/$unionWith/$sort` | Turns retrieved evidence into **one config decision** | The database decides, not Python |
| Change streams | Drive the live dashboard | Real-time split screen |

Remove MongoDB and there is no memory, no retrieval, no selection — the harness has no basis
for choosing a strategy.

### 9.2 Write path per attempt

1. Compute failing set, regression, `state_hash` (sha256 of allowlisted files), `patch_fingerprint`.
2. Insert `attempts` row; insert one `calls` row per external call.
3. On regression: restore parent state, set `rolled_back: true`.

### 9.3 Building development memory (checkpoints)

For each dev task:
1. Run under `focused` for two failed attempts (rollback on regression). Their summaries are
   the checkpoint's `prior_attempts`.
2. **Reset to seed** exactly as a strategy switch does (§6.2 step 4, same reset + seed-hash
   assert). The checkpoint is the seed plus the failure history, not the dirty tree.
3. Fork 4 workspaces from the seed. Run **one attempt per config, concurrently**. All four see
   identical `prior_attempts` text and the reset line — the same situation an eval run is in
   right after a switch. Each outcome records `solved` (diagnostics) and `verified` (protected
   tests + the static caller-inspection check, run only if diagnostics pass). Dev tasks only.
4. **Narrator call** writes `failure_narrative` from the **task, not the agent's edits**: seed
   code, seed failing tests (name + first error line), the pinned focal's name, and the diff of
   the first verified trial in registry order (`root_cause_from`). It never describes code
   after failed attempts (Gate 6: helpers a `focused` hack created made a family-B narrative
   read as family A). 2–3 sentences, *structural* only: no identifiers, paths, domain nouns,
   test names, exception names or literals (dev and eval domains differ; Gate 1 showed
   clustering by domain). A validator (`narrator.validate_narrative`) rejects any token from
   `error_symbols`, the task's file/package names or defined names, or anything
   identifier-shaped; one retry with the violations listed.
   `error_symbols` come from the seed baseline only: focal name, failing test names,
   exception types — never from an agent's edits.
5. Publish the checkpoint only after all four finish. Infra error = missing evidence, not failure.

**Build policy: a diagnostics pass ends the history.** If `focused` passes diagnostics during a
build, the checkpoint's history is the failed attempts before it (none → no checkpoint). The
build never consults protected results to decide what counts as a failed attempt, because
protected results must never feed the loop; the eval loop likewise stops at a diagnostics pass.

**Narrator-only changes re-narrate; they never re-run attempts.** A change to the narrator
prompt or to how `error_symbols` are built regenerates `failure_narrative` / `error_symbols` of
the frozen snapshot in place (`scripts/renarrate_snapshot.py`: narrator calls only; the fix
diff comes from each checkpoint's own verified trial, re-verified first; waits until the new
text is embedded and indexed). Attempts, `prior_attempts` and outcomes stay untouched, so the
evidence is not re-sampled.
6. Insert; poll until searchable (embeddings are async).
7. Freeze: `snapshot_id = "mem-v1"`. Evaluation never writes to `checkpoints`.

**The query narrative at eval time comes from the same narrator prompt and the same inputs**
(seed code, seed failing tests, focal name), except that the verified fix is "not known".
Known asymmetry: memory narratives can carry a sentence about where the defect was; query
narratives cannot. The organization + failure-shape sentences are what must match.

Budget: 4 dev checkpoints (2 per family) × 4 configs = 16 trials + 8 attempts to reach them.

### 9.4 Retrieval settings (frozen)

Semantic branch: `$vectorSearch` on `failure_narrative`, `limit 4`, `numCandidates 40`.
Lexical branch: `$search` on `error_symbols`, `limit 4`. Equal weights.
Both filtered by `snapshot_id` and `compat.protocol` **inside** the search stage.
Final neighborhood: **top 2** checkpoints, chosen **before** excluding tried configs.

### 9.5 Selection pipeline (`pipelines.py`) — ranks every untried config; row 0 is the choice

```python
def selection_pipeline(narrative, symbols, snapshot_id, protocol, registry, tried):
    return [
      {"$rankFusion": {
        "input": {"pipelines": {
          "semantic": [{"$vectorSearch": {
              "index": "ckpt_vec", "path": "failure_narrative",
              "query": narrative, "numCandidates": 40, "limit": 4,
              "filter": {"snapshot_id": snapshot_id, "compat.protocol": protocol}}}],
          "lexical": [
              {"$search": {"index": "ckpt_text", "compound": {
                  "must":   [{"text": {"query": symbols, "path": "error_symbols"}}],
                  "filter": [{"equals": {"path": "snapshot_id", "value": snapshot_id}},
                             {"equals": {"path": "compat.protocol", "value": protocol}}]}}},
              {"$limit": 4}]}},
        "combination": {"weights": {"semantic": 1, "lexical": 1}},
        "scoreDetails": True}},
      {"$limit": 2},
      {"$project": {"checkpoint_id": 1, "fusion": {"$meta": "scoreDetails"},
          "outcomes": {"$filter": {"input": "$outcomes",
              "cond": {"$not": {"$in": ["$$this.config_id", tried]}}}}}},
      {"$setWindowFields": {"sortBy": {"fusion.value": -1},       # rank 1 = nearest neighbour
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
      {"$sort": {"score": -1, "nearest_solve_rank": 1, "mean_cost": 1, "order": 1}}]
```

Notes:
- `tried`, `snapshot_id`, `registry` are parameters. Never literals.
- `$unionWith` guarantees unseen configs exist even if retrieval returns nothing
  (`$group` alone can never produce a config with no observations).
- `mean_cost: 1e9` sentinel — `null` sorts first ascending and would let unknowns win ties.
- Negative outcomes stay in: relevance at retrieval, outcome preference at aggregation.
- A solve counts only if `solved AND verified`: a memory that credits a config for a fix the
  protected tests reject teaches the wrong lesson. Formula unchanged. (Decided before any
  measurement.)
- **Tie-break by rank, not cost.** On a score tie, the config verified-solved by the nearest
  neighbour (lowest fusion rank) wins; `mean_cost` decides only when rank can't. With a
  mixed-family top 2, each family's winner gets one solve and they tie; the old cost tie-break
  then always picked `dependency` (family-B trials are cheap) — wrong for family A.
- No final `$limit`: the pipeline returns the full sorted candidate table; Python takes row 0
  and stores the table in `decisions.candidates` for the dashboard. `retrieved` (with fusion
  scores) comes from `retrieval_pipeline()`, which shares the same `$rankFusion` stage.
- Python labels `insufficient_evidence` if fewer than 2 checkpoints came back.
  Empty result → `configurations_exhausted` → stop.
- **Gate 1 must verify** `$vectorSearch` with `autoEmbed` works *inside* `$rankFusion`.
  Fallback: manual Voyage embeddings (`VOYAGE_BASE_URL`, `voyage-4`) + `queryVector`. Disclose.

---

## 10. Jev integration (`jev.py`) — planned; replaced by a rule at Gate 5

> **Gate 5 result (disclosed).** 10 dev cases (5 repeats incl. 2 same-function shrinking hacks;
> 5 non-repeats incl. 3 same-function refinements), 3 phrasings, 2 samples each. Hard-boundary
> gap (shrinking hacks vs refinements): p1 −0.03, p2 −0.23, p3 −0.36. p1 met the count gate
> (9/10 at THETA 0.15) only with THETA inside Jev's sampling noise and missed one shrinking
> hack (p=0.10). Control flow uses the §6.1 step-9 rule instead (9/10, 0 refinements flagged,
> deterministic). `jev.py` and `scripts/jev_smoke.py` stay as the evidence.

```python
POST https://openrouter.ai/api/alpha/decisions
{"model": "typesafe/jev-1.13",
 "state": <packet>,
 "questions": {
   "repeating": {"type": "noul",
     "instructions": "Is the latest attempt the same strategy as an earlier failed attempt, without using new information?",
     "criteria": {
       "true":  "Edits the same code with the same idea, e.g. adjusting rounding again, with no new context examined and no new tests passing.",
       "false": "Moves where the fix is applied, uses newly examined code, or makes measurable test progress."}},
   "failure_shape": {"type": "choice",
     "instructions": "Which pattern best describes the attempts?",
     "criteria": {"oscillation": "Fixing one test breaks another, then reverts.",
                  "no_progress": "Different edits, same failing tests.",
                  "partial_progress": "Failures shrinking."}}}}
```

- `answers.repeating.noul` = probability of yes. Control flow uses **only** this.
  `failure_shape` is dashboard display only.
- **Packet:** goal; current config; last 2 attempts under this config (functions edited,
  diff excerpt ≤60 lines, tests before/after); context examined; budget remaining; plus one
  older attempt if its fingerprint resembles the latest; `failing_before`, `failing_after`,
  `shrank` for the latest attempt (§6.1 step 9). Jev context is 32k tokens.
- **THETA:** chosen on 10 dev smoke cases (mix of repeats and legitimate refinements), then
  frozen. Gate: ≥8/10 correct, ≤1 refinement falsely flagged. Report as "passed smoke test",
  never as accuracy.
- Pin `jev-1.13`, never the `-latest` alias (thresholds must stay stable).
- Timeout/HTTP error → treat as not repeating, log `jev_unavailable`. Never intervene on
  missing evidence.
- Cost from `usage.cost` (input tokens only; output is free).
- Jev's own flags are never ground truth for semantic repetition in the evaluation.

---

## 11. Test runner (`runner.py`)

Interface (so a cloud runner can slot in later):
```python
class Runner(Protocol):
    def prepare(self, task, state) -> Workspace: ...
    def run(self, ws, cmd, timeout_s) -> TestReport: ...
    def fork(self, ws, n) -> list[Workspace]: ...
```
`LocalRunner`: `shutil.copytree` into a temp dir; `subprocess.run` with timeout;
`pytest --json-report --json-report-file=...`.

- **Diagnostic tests**: visible to the agent's feedback, live in the task repo, not editable.
- **Protected tests**: stored outside every workspace (`tasks/<id>/protected/`). After the
  loop, the verifier copies final source into a fresh dir, adds protected tests, runs them.
- **Static check in verification**: the lines the final diff adds (vs the seed) are grepped
  for gaming patterns (`runner.GAMING_PATTERNS`): caller/stack inspection (`sys._getframe`,
  `inspect.stack/currentframe/...`, `f_back`, `f_code`, `co_name`, `traceback.*stack`), module/
  source inspection, test-context sniffing (`PYTEST*`, `os.environ`/`getenv`, importing
  `pytest`/`tests`/`test_*`/`conftest`, `sys.modules`, `sys.argv`, `__import__`/`importlib`,
  string literals naming tests). Any match fails verification (`static::gaming_pattern`),
  whatever the tests say. Environment sniffing cannot be caught by tests at all (protected
  tests also run under pytest); this check is the only defence.
- **Workspaces are git worktrees**: `prepare` commits the seed and records its tree hash; the
  reset-on-switch (§6.2) restores it and asserts the hash.
- Later: Daytona (sub-90ms sandboxes, copy-on-write fork = our "4 configs from one
  checkpoint"). Don't build it today.

---

## 12. Task suite (`tasks/`)

Two families, 4 tasks each: 2 dev + 2 eval. 8 tasks total.

**Family A — oscillation.** A shared function has two callers with different expectations
(e.g. one passes cents, one passes dollars). Patching the shared function fixes one caller's
test and breaks the other's. Correct fix is at a call site. `caller` context should help.

**Family B — semantic repetition.** The bug is in a helper or data structure the focal
function depends on. The agent keeps making different-looking local edits in the focal
function (rounding 2→3, reorder ops, cast types) with no progress. Rules see "different
diffs"; Jev should see "same strategy". `dependency` context should help.

Each task directory:
```
tasks/<task_id>/
  task.json          # task_id, family, split, allowlist, diag_cmd, protected_cmd, goal
  repo/              # source + diagnostic tests (seeded bug)
  protected/         # protected tests, never copied into a workspace
  reference.patch    # reference fix; never in memory, never shown to the agent
```
Validation per task: seeded repo fails diagnostics; reference fix passes diagnostics AND
protected tests. Eval tasks use different code and domains than dev tasks — not renames.
Generating tasks with a model is fine; every task is verified by running it.

Designate the demo walkthrough task **when freezing the suite**, before seeing results.

---

## 13. Evaluation protocol

Three arms, same tasks, same model snapshot, same budget, separate workspaces:

| Arm | Behavior |
|---|---|
| `plain_retry` | No harness. Feed test output back, retry up to budget |
| `fallback` | Full Reflex ladder, but intervention picks next config by fixed registry order |
| `memory` | Full Reflex; intervention uses the MongoDB selection pipeline |

`plain_retry` vs `memory` proves the harness matters. `fallback` vs `memory` proves
MongoDB matters.

**Shared attempt 1.** The first `focused` attempt (no history, same prompt in every arm) is
generated once per task (`controller.shared_first_attempt`, its own run id and one `calls`
row) and replayed in `plain_retry`, `fallback` and `memory`: same patch applied to each arm's
own fresh seed, tests re-run, no new model call. Arms therefore differ only after attempt 1.
Each arm's `runs.cost_usd` includes the shared attempt's cost (`runs.shared_attempt`), so cost
per verified fix stays comparable.

Order: freeze memory snapshot, THETA, prompts, registry, retrieval settings, scoring →
then run eval. **No tuning after seeing eval results.** One run per task per arm; any rerun
is counted and reported.

### 13.1 Metrics

Primary: **tasks solved (verified by protected tests)**, shown as "X of N", always with N.
Headline: **cost per verified fix** = total eval cost of the arm (including failed tasks) ÷
verified solves. Always show total spend and solve count next to it.
Secondary: attempts spent on never-solved tasks (pure waste), repeated failed attempts,
regressions, attempts to solve.
Memory-building cost reported separately.
Elapsed time only for eval runs (dev trials run concurrently and distort timing).

### 13.2 Cost accounting (`calls`)

Every external call writes: `component` (agent | narrator | jev | embed), dated model,
input/output tokens, `cost_usd`, latency.
- Coding model & narrator: compute tokens × pinned list price (`prices.py`), and also log
  OpenRouter's `usage.cost`. BYOK routing can make `usage.cost` misleading.
- Jev: `usage.cost`.
- Automated Embedding query: estimate narrative tokens × voyage-4 price ($0.06/M).
Dashboard shows a "where the harness spends" breakdown.

### 13.3 If Reflex loses

Report it: "no measured improvement at this sample size; here's where the overhead went."
Four held-out tasks are directional evidence, not proof. Say "on N held-out tasks" out loud.

**Sample size, stated up front.** Memory holds **N=2 checkpoints per family** (4 total), and
retrieval takes the top 2. Fallback's first switch (`caller`) is right for family A, so memory
and fallback are expected to tie there; any memory-vs-fallback difference rests on the **2
family-B eval tasks**. Gate 8 is a **feasibility result, not proof that memory beats
fallback.** Cross-family neighbour risk: with 2 checkpoints per family, the #2 neighbour can
come from the other family (seen at Gates 1 and 7), diluting the evidence behind a choice.

**Leave-one-out preview, first run (dev only, `scripts/loo_retrieval.py`).** Eval-style queries on the 4
dev tasks with their own checkpoint excluded: top-1 same family **3/4**; top-2 mixed in every
case. Family A separates clearly (semantic 0.83 vs ≤ 0.77); family B barely or not at all
(margins 0.01–0.03); sem-dev-02's query ("a shared aggregation function… reused by several
functions") retrieved two family-A checkpoints. LOO leaves one same-family checkpoint per
query; eval has two.

### 13.4 Gate 8 predictions (written before any eval run)

- **Family A (oscillation): memory ≈ fallback.** Both switch to `caller` when a trigger fires
  (fallback by registry order, memory by evidence). Memory can misroute only if a family-A
  query's top-1 neighbour is family B (final LOO: osc-dev-01's top-1 was family B by 0.001).
- **Family B (semantic repetition): memory > fallback only when the switch happens by attempt 2
  and top-1 is same-family.** Fallback's first switch is `caller`, which cannot see the helper.
  A switch at attempt 3 leaves no budget; a cross-family top-1 sends memory to `caller` too.
- **Runs that end before selection can act are identical across arms**, e.g. a hack that passes
  diagnostics before any switch (osc-dev-01 did this in every dev smoke run). They count, and
  are reported as such.
- **N=2 checkpoints per family, 2 eval tasks per family. Gate 8 is a feasibility result, not
  proof that memory beats fallback.**
- Dev smoke reference (self-retrieval, plumbing only — not a prediction): plain_retry 0/4,
  fallback 1/4, memory 3/4.

**Pre-registered Gate 8 protocol (this commit; before any eval run).**
- Frozen: code `26b79a7` + mem-v1 `c701ea5ef355eb7bce1195498978532cf1003b5bfc368b2f4a03173899646bce`.
  No change to code, tests or memory during or after the run; if something breaks, stop.
- **5 repeats per eval task per arm** (4 eval tasks × 3 arms × 5 = 60 runs). Within a repeat,
  attempt 1 is generated once per task and shared across the three arms; it is fresh per
  repeat. Implemented as 5 sequential `scripts/run_suite.py --split eval --phase eval` runs.
- **Primary metric: verified rate per arm per family over all repeats** (verified / 10 runs per
  arm per family). Secondary: total cost and cost per verified fix per arm. Repeats re-sample
  the model on the same tasks: 10 runs per cell come from **2 distinct tasks per family**.
- **Per run:** switch attempt; top-1/top-2 families and scores and the margin; chosen vs
  designed config; whether the run ended before selection could act. Scores = logged fusion
  scores. **Margin = semantic score (vectorSearchScore) of top-1 minus top-2**, recomputed
  after the run from the run's logged query narrative (read-only), because with the lexical
  branch empty the RRF fusion margin is set by rank alone (1/61 − 1/62).
- Memory on family B is broken down by same-family vs cross-family top-1.
- **Retrieval is effectively semantic-only:** after the exception stoplist the lexical branch
  had zero matches in the final leave-one-out, and dev and eval tasks share no identifiers.
- **Dev smoke results are not evidence:** each dev task retrieved its own checkpoint.

**Logged on every eval run (`runs`).** `switch_attempt` (or null = never) and `triggers`;
`neighbours` = top-1/top-2 checkpoint, family and fusion score (memory arm; other arms do not
retrieve, so null); `chosen_config` vs `designed_config` and `chosen_matches_designed`;
`pre_selection_end` = why selection never acted (`diagnostics_passed_before_switch (...)`,
`no_trigger`, `trigger_at_final_attempt`, `arm_has_no_selection` for plain_retry), null when it
acted. Attempt 1 is shared across arms (`shared_attempt`).

### 13.5 Gate 8 results (frozen `26b79a7` + mem-v1 `c701ea5e`, pre-registered at `67bc540`)

**Feasibility result on 4 held-out tasks** (2 per family, 5 repeats each). Repeats re-sample the
model on the same tasks and are not independent: **effective N = 2 tasks per family.** No
significance claims. Artifacts: `results/gate8/` (report, per-run JSON, logs; sha256 in
`results/gate8/MANIFEST.md`; `report.txt` sha256 `0aa6e13b…20a8`).

| Arm | Family A (oscillation) | Family B (semantic repetition) | All | Cost | Cost / verified fix |
|---|---|---|---|---|---|
| plain_retry | 0/10 | 0/10 | 0/20 | $0.0647 | — |
| fallback | 4/10 | 0/10 | 4/20 | $0.0391 | $0.0098 |
| memory | 5/10 | 8/10 | 13/20 | $0.0366 | $0.0028 |

Verified = diagnostics AND protected tests pass (plus the static gaming-pattern check).
Per task (verified/5): osc-eval-01 plain 0, fallback 1, memory 2; osc-eval-02 plain 0,
fallback 3, memory 3; sem-eval-01 plain 0, fallback 0, memory 5; sem-eval-02 plain 0,
fallback 0, memory 3.

**Core finding: memory-guided selection is only as good as retrieval.** When memory's top-1
neighbour was same-family it chose the designed config every time (**13/13** across both
families, all verified); when top-1 was cross-family it chose wrong (**0/2**, both on
sem-eval-02, semantic margins 0.047 and 0.060).

**Family B: memory 8/10 vs fallback 0/10.** Fallback's fixed order switches to `caller`
first, and `caller` never shows the helper file where family B's defect lives — it cannot
succeed on B by design. The fair comparison is a random choice among the three untried configs:
**analytical baseline ≈ 1/3 (≈ 3.3/10) — computed, not run**, assuming P(verify | dependency) ≈ 1
(8/8 observed) and P(verify | caller or diagnostic) ≈ 0 (caller 0/10 at eval; diagnostic never
verified in family-B dev trials).

**Family A: memory ≈ fallback.** Every switch in both arms chose `caller` and verified
(fallback 4/4, memory 5/5; memory's top-1 was same-family 5/5). The 5 vs 4 difference comes
entirely from runs that ended before selection could act (fallback 6, memory 5), where each
arm's independently sampled attempt 2 passed diagnostics with a hack.

**Protected verification decides family A.** 11 of 20 switching-arm runs on family A ended
with a hack that passed diagnostics and failed the protected tests. Plain retry ended
`verification_failed` in 9/10 family-A runs: scored on diagnostics alone it would be **~9/10**
on family A; under the verified-fix standard it is **0/10**.

**Explicit non-claims.**
- **No eval evidence for repeated-strategy detection on family B.** All 20 family-B switches
  (fallback and memory) were regression triggers at attempt 1 — the shared attempt 1 regressed
  in every repeat on both family-B tasks. The same-strategy rule fired 3 times in all of
  Gate 8, all on family A (osc-eval-01, attempt 2). Gate 8 tests strategy *selection*.
- **Retrieval was effectively semantic-only.** After the exception stoplist, the lexical
  branch matched nothing (dev and eval share no identifiers); `$rankFusion` ranked by the
  semantic branch alone.
- Dev smoke results are not evidence (each dev task retrieved its own checkpoint).
- Reflex does not fix model generalization; it changes the context the model gets.

**Future work.**
- A fixed query per task: the query narrative is regenerated by the narrator on each run, so
  the same task retrieved differently across repeats (the two misroutes).
- More checkpoints per family (N=2 per family leaves one bad neighbour decisive).
- Tasks where attempt 1 does not regress, so the repeated-strategy detection is actually tested.
- A random-selection arm, run for real rather than computed.

---

## 14. Dashboard & demo

Dashboard (`dashboard/`): FastAPI, one change stream on `attempts` + `decisions`, SSE to one
HTML page. Panels: per-arm attempt timeline (red/green), current config, trigger that fired,
Jev probability + failure_shape, **retrieved checkpoints with narratives and fusion scores
beside the current narrative**, candidate table (support/solves/regressions/score), chosen
config, cost breakdown, final comparison table.

Demo video (60s), pre-recorded from real runs:
- 0–15s: `plain_retry` on the walkthrough task — fix, break, revert, budget gone.
- 15–35s: `memory` on the same task — two failed attempts → Jev fires → retrieved evidence
  on screen → config switches to `caller` → attempt 3 green.
- 35–50s: comparison table across all eval tasks and three arms, with N.
- 50–60s: "In production this is a Claude Code stop hook — the agent stays yours, Reflex watches."

Label the walkthrough as a selected example. Show the full frozen results after it.

---

## 15. Repo layout

```
reflex_harness/
  __init__.py
  config.py        # env loading, constants (THETA, budgets, snapshot ids)
  store.py         # pymongo client, collection helpers, inserts
  pipelines.py     # selection_pipeline(), other aggregations — pure functions
  context.py       # ast-based focal/caller/dependency resolution, prompt blocks
  agent.py         # OpenRouter chat call, JSON parsing, allowlist enforcement
  runner.py        # Runner protocol, LocalRunner, pytest JSON parsing
  jev.py           # packet builder, Decisions API call
  narrator.py      # failure_narrative + error_symbols
  controller.py    # the loop and decide() ladder
  prices.py        # pinned per-model prices
  cli.py           # python -m reflex_harness run --task X --arm memory
scripts/
  check_connection.py, smoke_test.py, mcp-mongodb.sh, install-mongodb-skills.sh
  create_indexes.py   # both search indexes + regular indexes, idempotent
  seed_configs.py     # the four configs, registry r1
  build_memory.py     # dev checkpoints → mem-v1
  run_eval.py         # all eval tasks × 3 arms
  jev_smoke.py        # 10 cases, choose THETA
tasks/               # task suite (see §12)
dashboard/
docs/SPEC.md         # this file
CLAUDE.md            # schemas, indexes, coding rules
```

---

## 16. Build gates (do not skip ahead)

| # | Gate | Passes when |
|---|---|---|
| 0 | Connectivity | `scripts/smoke_test.py` 4/4 |
| 1 | Atlas retrieval | Both indexes built; fixture checkpoints searchable; paraphrased narrative retrieves the right one via `$rankFusion`; selection pipeline returns a config; changing an outcome changes the choice. Fixtures are plumbing, never results — delete before building memory |
| 2 | Runner + evaluator | A patch can pass or fail; allowlist rejects test edits; protected verification works |
| 3 | Configs + context | Same checkpoint runs under all 4 configs with visibly different prompts |
| 4 | Tasks | 8 tasks validated (seed fails, reference passes); model calibration: `focused` fails, the right config succeeds on at least one dev task |
| 5 | Jev | Smoke test passes; THETA frozen. If it fails: ship rules-only, say so |
| 6 | Memory | 4 checkpoints × 4 trials stored; snapshot frozen |
| 7 | Loop | End-to-end run shows an observable evidence-driven config switch |
| 8 | Evaluation | 3 arms on eval tasks; results table. Feasibility at N=2 per family, not proof (§13.3) |
| 9 | Dashboard + video + submission | Public repo, video with audio, description |

Kick off memory building (gate 6) in the background as soon as gates 2–4 pass; build the
loop and dashboard while it runs. Reserve the last quarter of the day for eval, recording,
submission. No new features in that window.

---

## 17. Contingencies (decided in advance)

| If | Then |
|---|---|
| `autoEmbed` fails or is blocked by sandbox policy | Ask MongoDB staff immediately; fallback to manual Voyage + `queryVector`; disclose |
| `$vectorSearch` won't run inside `$rankFusion` | Run branches separately, fuse with RRF in Python; disclose |
| Jev fails smoke gate | Rules-only; Jev shown as future work. **Taken at Gate 5** (§10) |
| Model solves everything under `focused` | Weaker model; re-calibrate |
| Model fails even with right context | Stronger model (`google/gemini-3.8-flash-20260902`) |
| One config wins everywhere | Report it; don't manufacture an adaptive benefit |
| Retrieval returns < 2 checkpoints | Registry order, labelled `insufficient_evidence` |
| Memory shows no improvement | Report measured result + failure analysis |

---

## 18. Production path (one slide, not built today)

Claude Code **stop hook**: when the agent says "done", the hook runs tests, records the
attempt, runs the same `decide()`. Tests pass → exit 0. Repeating → block with a reason that
injects the selected context ("You've tried rounding twice. Here is the caller: ...").
Same brain, same MongoDB, same Jev. The user's workflow doesn't change.
Structure `decide()` as one pure function now so the hook is ~30 lines later.
Cloud runner: Daytona behind the `Runner` protocol.

---

## 19. Honesty rules

- Never claim Reflex uses fewer tokens. Claim cost per verified fix, measured.
- Always show N. Four held-out tasks is directional.
- Fixtures are never results. Jev flags are never ground truth.
- Disclose every fallback taken (manual embeddings, manifests, rules-only).
- No tuning on the eval set. Report reruns.
- Reflex improves the repair process; it does not fix model generalization.

---

## 20. Glossary

- **Attempt**: one patch + one diagnostic run.
- **Checkpoint**: a frozen dev failure state with measured outcomes of all 4 configs from it.
- **Snapshot** (`mem-v1`): the frozen set of checkpoints evaluation retrieves from.
- **Trigger**: what caused an intervention — `regression`, `exact_repeat`, `jev`.
- **Support**: number of retrieved checkpoints with an observed outcome for a config.
- **Verified fix**: diagnostics pass AND protected tests pass.
- **THETA**: frozen Jev probability threshold for "repeating".

---

## 21. Changelog (changes after the plan freeze; all decided on dev evidence, before any eval run)

| When (Sept 26, ET) | Change | Reason |
|---|---|---|
| ~11:15 | Selection: a solve = `solved AND verified`; outcomes record both | A diagnostics-only fix (e.g. truncation instead of rounding) would teach memory the wrong lesson |
| ~11:15 | Selection pipeline returns the full sorted candidate table (no final `$limit`) | `decisions.candidates` and the dashboard need it |
| ~11:15 | Narrator: structural pattern only, no identifiers/paths/domain nouns/test names; validator + one retry | Gate 1: retrieval clustered by domain, not failure pattern; dev and eval domains differ |
| ~11:15 | Focal chain: traceback → `context_manifest.json`; `focal_source` recorded | Assertion-only failures have no source frame |
| ~11:15 | `focused`/`diagnostic` see a filtered traceback; `caller`/`dependency` see it in full | Caller frames leaked into `focused`, making configs not really different |
| ~11:15 | Diagnostic check script runs from a scratch dir against a throwaway copy | Arbitrary code must not bypass the allowlist or enter the patch |
| ~11:45 | Focal pinned once per task from the seed baseline; `re-resolved` if it disappears | Per-attempt focal drifted to downstream victims (`apply_tax` → `format_cents`) |
| ~12:00 | Ladder step 7: shrinkage continues only if the patch moved to a new function; otherwise it goes to Jev with `shrank: true` | sem-dev-02 calibration: a same-function rounding hack shrank failures 3 → 1, so the old step 7 skipped Jev on exactly the family that separates memory from fallback |
| ~12:20 | Ladder step 9: rule-based same-strategy detector replaces Jev; trigger `same_strategy` | Gate 5: Jev's hard-boundary gap was negative for all 3 phrasings (p1 −0.03, within sampling noise); rule scored 9/10 with 0 refinements flagged on the same cases |
| ~12:55 | Reset-on-switch: every switch resets the worktree to the seed (`git checkout -- .` + `git clean -fd`), asserts tree hash == seed hash (else `reset_failed`), logs the reset in the decisions row, and adds a reset line to the new config's first prompt; memory trials fork from the seed the same way | Dev: `dependency` (sem-dev-02) and `caller` (osc-dev-01) produced correct root-cause fixes that failed verification only because the abandoned strategy's edits were left in the tree. Deliberate simplification: we isolate strategy selection, not dirty-tree recovery |
| ~13:00 | Narratives built from the task (seed code, seed failing tests, verified fix diff), never from the agent's edits; `error_symbols` from the seed baseline; eval query uses the same prompt with the fix "not known" | Gate 6: a `focused` hack created a helper, so sem-dev-01's narrative read as family A ("shared helper used by multiple callers") and its symbols carried hack names |
| ~13:05 | Family-B protected tests: one probe per task that exercises the helper from a non-`test_` function; standing static check fails verification on caller/stack inspection in the final diff | Audit (`scripts/audit_gaming.py`): a test-sniffing hack (correct only when the caller's name starts with `test_`) passed sem-dev-01's protected tests; same idea would pass the other three. After the change: 0 of 16 gaming patches pass; every stack-inspecting one is also flagged statically |
| ~13:25 | **FREEZE (pre-Gate 8): code `bcecbc7` + mem-v1 sha256 `84cbf2b11c664bc373f73b8c36c80b99bbb0b2a8f392fa4689ef61b964b63619`** (4 checkpoints; `scripts/snapshot_hash.py`). Old mem-v1 archived in `checkpoints_archive` as invalid (weak tests) | Ladder, same-strategy rule, selection scoring, prompts, narrator and memory fixed before any eval run. Rebuilt mem-v1: exactly one verified config per dev task (caller: osc-dev-01, osc-dev-02; dependency: sem-dev-01, sem-dev-02); build cost $0.018 |
| ~13:50 | Leave-one-out retrieval preview on dev (no eval) | Before changing selection: top-1 same family 3/4, top-2 always mixed, family-B margins 0.01–0.03 |
| ~13:55 | Selection tie-break: on a score tie, the nearest neighbour's (lowest fusion rank) verified config wins; `mean_cost` only when rank can't decide | With a mixed top 2 each family's winner tied and the cost tie-break always chose `dependency` (cheap family-B trials) — deterministic misrouting of family A. Gate 1 now forces a tie: rank-1 `caller` ($0.09) beats rank-2 `dependency` ($0.01) |
| ~14:00 | Same-strategy rule uses a focal region: pinned focal + functions the agent created this run; fires when both attempts' edits stay inside and failures remain | Dev smoke: sem-dev-01 never intervened in any arm — the agent moved its hack into a helper it created, so "same focal function edited" never held |
| ~14:05 | Attempt 1 shared across arms (generated once per task, replayed; cost attributed to every arm) | Arms got different attempt-1 behaviour on the same task (osc-dev-01: fallback regressed and switched, memory hacked diagnostics and stopped), so arm differences reflected sampling before any selection happened |
| ~14:10 | Static check extended to test-context sniffing (PYTEST env, os.environ, test-module imports, sys.modules/argv, dynamic import, test-name literals); prompt summaries no longer end in ".." | Environment sniffing passes every protected test (they run under pytest); audit: 2 such hacks caught by the static check only, 0 holes |
| ~14:20 | **FREEZE (pre-Gate 8, supersedes the ~13:25 freeze): code `37bf092` + mem-v1 sha256 `84cbf2b11c664bc373f73b8c36c80b99bbb0b2a8f392fa4689ef61b964b63619`** (unchanged; 4 checkpoints) | Tie-break by rank, focal-region rule, shared attempt 1, test-context static check. Dev smoke (self-retrieval, plumbing only): plain_retry 0/4, fallback 1/4, memory 2/4 |
| ~14:40 | Focal region adds seed functions the failing tests call directly; step 7 "moved" = edit outside the focal region | Smoke: sem-dev-01's shared attempt 1 also rewrote a seed sibling (`pass_rate`) the failing tests call, so the region rule fired only at attempt 3; a shrinking hack moved into a new helper would have counted as "moved" |
| ~14:45 | Narrator: never mention whether a fix is known; built-in exception names stoplisted from `error_symbols` (both memory and query) | Eval-style queries said "no verified fix is provided"; exception names (AssertionError in almost every task) only added cross-family lexical noise |
| ~14:50 | Build policy: a diagnostics pass ends a build's history (failed attempts before it) | A rebuild lost osc-dev-01's checkpoint because `focused` hacked diagnostics at attempt 2; protected results must never decide what counts as failed |
| ~14:55 | mem-v1 restored from 84cbf2b1 (hash re-verified) and **re-narrated in place** (narrator calls only; evidence untouched); the 3-checkpoint rebuild ec6fa15b archived as superseded | The build never runs the ladder, so the region/step-7 changes cannot alter trial outcomes; only narratives and symbols changed. New content hash `c701ea5e…` |
| ~15:00 | Per-run Gate 8 logging (`switch_attempt`, `triggers`, `neighbours`, chosen vs designed config, `pre_selection_end`) and §13.4 predictions | Written before any eval run so results are read against stated expectations |
| ~15:00 | Final leave-one-out (report only, no tuning): top-1 same family 3/4 (the miss moved from sem-dev-02 to osc-dev-01, margin 0.001); lexical branch matched nothing after the stoplist | Queries are regenerated by the narrator on each run, so LOO varies run to run at these margins |
| ~15:05 | **FINAL FREEZE before Gate 8: code `26b79a7` + mem-v1 sha256 `c701ea5ef355eb7bce1195498978532cf1003b5bfc368b2f4a03173899646bce`** (4 checkpoints: 84cbf2b1 evidence, re-narrated). No harness changes after this point, whatever Gate 8 shows | Supersedes the 37bf092 freeze |
| ~15:15 | **Gate 8 pre-registration** (§13.4): 5 repeats per eval task per arm, attempt 1 shared within a repeat and fresh per repeat; primary metric verified rate per arm per family; semantic-score margin; retrieval semantic-only; dev smoke not evidence | Supersedes §13's "one run per task per arm": at N=2 tasks per family a single run per cell is dominated by sampling. Docs + .gitignore only; code stays `26b79a7` |
| ~15:55 | **Gate 8 results recorded** (§13.5, `results/gate8/`, README). Docs only | Frozen `26b79a7` + mem-v1 `c701ea5e`, pre-registered `67bc540`; mem-v1 hash unchanged after the run |

