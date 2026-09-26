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
7. **Strict-subset progress?** Failing set is a strict subset of previous failing set, same
   suite, no missing/skipped tests → continue. (3 failures → 2 *different* failures is NOT progress.)
8. **Too early for Jev?** Already switched, or fewer than 2 completed attempts under the
   current config → continue.
9. **Ask Jev.** `p(repeating) >= THETA` → trigger = `jev` → intervene. Else continue.

Controller-generated rollbacks are recorded separately and must never count as agent
oscillation. Log which trigger fired: "rules caught it" vs "Jev caught it" is evidence for
whether Jev earns its place.

### 6.2 Intervention

1. Build current failure narrative (same narrator prompt as dev memory — see §9.3).
2. Load `tried_config_ids` from **exact** current-task history (`attempts`), never from retrieval.
3. Run the selection pipeline (§9.5). It returns one `config_id` + evidence.
4. Write a `decisions` row. Load the config. `switched = True`, `attempts_in_config = 0`.
5. The new config gets at least one completed attempt before anything else can stop it,
   except diagnostics passing or budget exhaustion.

Stop reasons (store separately from `outcome`):
`solved`, `verification_failed`, `budget_exhausted`, `rolled_back_budget_exhausted`,
`intervention_limit_reached`, `configurations_exhausted`, `infrastructure_error`.

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
1. Run under `focused` until the second failed attempt. That workspace state = checkpoint.
2. **Narrator call** writes `failure_narrative`: 2–3 sentences of prose from diffs and test
   deltas describing the *structural* pattern only: no identifiers, paths, domain nouns or
   test names (dev and eval tasks use different domains; "refund"/"invoice" in a narrative
   hurts cross-domain retrieval — Gate 1 showed retrieval clustering by domain). Those belong
   in `error_symbols`, extracted separately (test names, exception types, function names).
   A cheap validator (`narrator.validate_narrative`) rejects a narrative containing any token
   from `error_symbols`, the task's file/package names or defined function/class names, or
   anything identifier-shaped; the narrator retries once with the violations listed.
3. Fork 4 workspaces from the checkpoint. Run **one attempt per config, concurrently**.
   All four see identical `prior_attempts` text. Each outcome records `solved` (diagnostics)
   and `verified` (protected tests, run only if diagnostics pass). Dev tasks only.
4. Publish the checkpoint only after all four finish. Infra error = missing evidence, not failure.
5. Insert; poll until searchable (embeddings are async).
6. Freeze: `snapshot_id = "mem-v1"`. Evaluation never writes to `checkpoints`.

**The query narrative at eval time must come from the same narrator prompt**, or stored and
query vectors describe different things and retrieval silently degrades.

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
      {"$unwind": "$outcomes"},
      {"$group": {"_id": "$outcomes.config_id", "support": {"$sum": 1},
          "solves": {"$sum": {"$cond": [
              {"$and": ["$outcomes.solved", "$outcomes.verified"]}, 1, 0]}},
          "regressions": {"$sum": {"$cond": ["$outcomes.regression", 1, 0]}},
          "mean_cost": {"$avg": "$outcomes.cost_usd"},
          "evidence": {"$push": "$checkpoint_id"}}},
      {"$unionWith": {"coll": "configs", "pipeline": [
          {"$match": {"registry": registry, "config_id": {"$nin": tried}}},
          {"$project": {"_id": "$config_id", "support": {"$literal": 0},
              "solves": {"$literal": 0}, "regressions": {"$literal": 0},
              "mean_cost": {"$literal": 1e9}, "order": 1}}]}},
      {"$group": {"_id": "$_id", "support": {"$max": "$support"},
          "solves": {"$max": "$solves"}, "regressions": {"$max": "$regressions"},
          "mean_cost": {"$min": "$mean_cost"}, "order": {"$max": "$order"},
          "evidence": {"$first": "$evidence"}}},
      {"$addFields": {"score": {"$divide": [
          {"$subtract": ["$solves", {"$multiply": [2, "$regressions"]}]},
          {"$add": ["$support", 1]}]}}},
      {"$sort": {"score": -1, "mean_cost": 1, "order": 1}}]
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
- No final `$limit`: the pipeline returns the full sorted candidate table; Python takes row 0
  and stores the table in `decisions.candidates` for the dashboard. `retrieved` (with fusion
  scores) comes from `retrieval_pipeline()`, which shares the same `$rankFusion` stage.
- Python labels `insufficient_evidence` if fewer than 2 checkpoints came back.
  Empty result → `configurations_exhausted` → stop.
- **Gate 1 must verify** `$vectorSearch` with `autoEmbed` works *inside* `$rankFusion`.
  Fallback: manual Voyage embeddings (`VOYAGE_BASE_URL`, `voyage-4`) + `queryVector`. Disclose.

---

## 10. Jev integration (`jev.py`)

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
  older attempt if its fingerprint resembles the latest. Jev context is 32k tokens.
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
| 8 | Evaluation | 3 arms on eval tasks; results table |
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
| Jev fails smoke gate | Rules-only; Jev shown as future work |
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
