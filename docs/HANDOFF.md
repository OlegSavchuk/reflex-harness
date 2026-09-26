> **Historical** — the session-start handoff. `docs/SPEC.md` is current. Since Gate 9 Phase 1
> retrieval is semantic-only (the `$search`/`$rankFusion` plan below was removed).

# Handoff — session state as of Sat Sept 26, ~10:50 ET

You are continuing work on **Reflex** (`reflex-harness`) at the MongoDB Harness Engineering
hackathon. Planning is finished and frozen. Setup is done. **No application code exists yet.**
Your job is to build it, gate by gate.

## Read in this order
1. `docs/SPEC.md` — the full build specification (architecture, decision ladder, selection
   pipeline, Jev contract, task suite, evaluation protocol, build gates, contingencies).
2. `CLAUDE.md` — MongoDB schemas, sample documents, indexes, coding rules, cluster facts.
3. This file — what's already done and what's next.

Do not redesign. If something in the spec looks wrong, say so and ask before changing it.

## The person
Oleh — software engineer, solo on this build. Wants direct, critical feedback ("ruthless
mentor"): stress-test, don't validate. Keep answers short. Don't end every message by asking
about event logistics. Commit only when asked.

## Timeline
- Hacking started ~10:00 ET. Submission deadline: check the event page / Discord (not recorded here).
- Reserve the last quarter of the day for evaluation, video recording, submission. No new
  features in that window.

## Environment (verified)
- Repo: `~/Repositories/reflex-harness` (macOS). Remote: `github.com/OlegSavchuk/reflex-harness`.
  Branch `main`, **no commits yet**. Must be public at submission.
- Python 3.10+ code. Create venv: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Atlas Hackathon Sandbox: M10, MongoDB 8.0.x, AWS, host `cluster0.kyzumw.mongodb.net`,
  DB user `olegsavchuk12_db_user`, database `reflex`. An org resource policy banner is shown
  in Atlas — some settings may be locked.
- `.env` (gitignored) is fully populated: `MONGODB_URI`, `MONGODB_DB=reflex`,
  `MDB_MCP_CONNECTION_STRING`, `MDB_MCP_READ_ONLY=true`, `OPENROUTER_API_KEY`,
  `CODING_MODEL=openai/gpt-6-luna-20260922`, `JEV_MODEL=typesafe/jev-1.13`,
  `VOYAGE_API_KEY` (Atlas-issued), `VOYAGE_BASE_URL=https://ai.mongodb.com/v1`.
  **Never print or commit `.env`.**
- OpenRouter: the user's OpenAI key is set as *Prioritized BYOK* → OpenAI model calls bill to
  that key, and `usage.cost` may be misleading. Compute cost as tokens × pinned price
  (`prices.py`) and also log `usage.cost`.

## Files that exist
```
.gitignore            .env, .env.*, .claude/skills/, .venv, runs/, workspaces/, *.log
.env.example          all variable names, no values
.mcp.json             MongoDB MCP server "mongodb" → bash scripts/mcp-mongodb.sh (read-only)
CLAUDE.md             schemas/indexes/rules; points to docs/SPEC.md
requirements.txt      pymongo, python-dotenv, requests, pytest, pytest-json-report, fastapi, uvicorn, voyageai
docs/SPEC.md          full specification
docs/HANDOFF.md       this file
scripts/check_connection.py      Atlas ping + version
scripts/smoke_test.py            Atlas r/w, coding model, Jev, Voyage — prints PASS/FAIL, no secrets
scripts/mcp-mongodb.sh           loads .env, starts mongodb-mcp-server@<3 read-only
scripts/install-mongodb-skills.sh  reinstalls MongoDB Agent Skills into .claude/skills
.claude/skills/       6 official MongoDB skills (gitignored): connection, mcp-setup,
                      natural-language-querying, query-optimizer, schema-design, search-and-ai
test.log              stray file from the user, ignored
```

## MongoDB tooling for you
- MongoDB MCP server is configured in `.mcp.json` as `mongodb`, read-only. Approve it when
  Claude Code prompts. Use it to inspect data and index status. **Create indexes via
  `scripts/create_indexes.py`, not MCP** (reproducibility).
- Needs Node ^20.19 / ^22.13 / >=24 on the Mac — check `node --version` if MCP fails to start.
- Use the skills in `.claude/skills/` (especially `mongodb-search-and-ai`) for index and query work.

## Decisions locked (short list — details in SPEC)
- Wrapper architecture: Reflex owns the loop; coding agent is a direct OpenRouter model call
  (NOT Claude Code/Codex) so Reflex controls exactly what context the model sees.
- Output format from model: full-file JSON replacements; allowlist enforced in code.
- Budget 3 attempts; max 1 config switch per task.
- 4 configs: focused → caller → dependency → diagnostic.
- Jev (not Laya) for the one semantic judgment, via `POST https://openrouter.ai/api/alpha/decisions`.
- Retrieval: autoEmbed (voyage-4) on `failure_narrative` + `$search` on `error_symbols`,
  `$rankFusion`, top-2 neighborhood, selection in one aggregation, score
  `(solves − 2·regressions)/(support+1)`, unknowns via `$unionWith` registry with `mean_cost 1e9`.
- Do NOT upgrade the cluster; `$rankFusion` works on 8.0. No `$scoreFusion`/`$rerank`.
- 8 tasks: 2 families (oscillation, semantic repetition) × (2 dev + 2 eval).
- 3 eval arms: `plain_retry`, `fallback`, `memory`. Headline metric: cost per verified fix, always with N.
- Production story (not built): Claude Code stop hook calling the same `decide()`.

## Open items / risks (in priority order)
1. **Gate 0 not yet confirmed.** User was about to run `python scripts/smoke_test.py`.
   Ask for its output first. Previous Claude session could not run it (sandbox had no network).
2. **Storage auto-scaling** must be ON in Atlas for Automated Embedding. May be blocked by the
   sandbox org policy — if so, ask MongoDB staff on-site immediately; fallback = manual Voyage
   embeddings + `queryVector` (disclose).
3. **Unverified:** that `$vectorSearch` with autoEmbed `query: "<text>"` works inside
   `$rankFusion`. This is Gate 1's main job.
4. **Model calibration:** Luna must fail under `focused` and succeed under the right config on
   at least one dev task. If it solves everything → weaker model; if it fails even with the
   right context → `google/gemini-3.8-flash-20260902`.
5. Task suite (8 tasks with protected tests + reference fixes) is the biggest time sink.

## Next steps (do in this order)
1. Get smoke test output from the user; fix anything that fails.
2. Gate 1: write `scripts/create_indexes.py` (vector `ckpt_vec` + search `ckpt_text` +
   regular indexes, idempotent), `scripts/seed_configs.py`, `reflex_harness/pipelines.py`
   with `selection_pipeline(...)`, and `scripts/gate1_retrieval.py` that inserts ~6 labelled
   fixture checkpoints, polls until searchable, runs a paraphrased query, prints retrieved
   IDs + chosen config, flips one outcome and shows the choice changes, then deletes fixtures.
3. Gate 2: `runner.py` (LocalRunner, pytest JSON parsing, protected verification).
4. Gates 3–4: `context.py`, `agent.py`, first two tasks, calibration run.
5. Then follow SPEC §16.

## First message to send in the new session
"Read docs/HANDOFF.md, docs/SPEC.md and CLAUDE.md. Here is my smoke test output: <paste>.
Then start Gate 1."
