# Multi-Agent AI Analyst — Project Plan

Course capstone (see `docs/rubric-source.html` reference — the guide from Telegram): LangGraph
supervisor + specialist agents (retriever/RAG, web search, text-to-SQL, code exec) + critic +
memory + eval harness (RAGAS/LLM-judge) + tracing (Langfuse) + deployed frontend. Graded /100,
see rubric in the guide doc.

**Deviation from the generic guide, on purpose:** the guide suggests free-tier throwaway hosts
(Colab+Gradio share, Render, Vercel). We're using the froton VPS instead for everything except
LLM/vector-DB/search/tracing SaaS (those stay on their own free tiers — no reason to self-host
Postgres+ClickHouse+Redis for Langfuse on a shared 8GB box). See "Infra decisions" below.

## Open questions — resolved

1. **Frontend: Gradio-first vs. build the real thing once.**
   → Skip Gradio. Build a small Vue 3 + Vite SPA from the start, same stack as `tezyodla/tyfront`
   (already deployed on this VPS, same Caddy pattern, same build/deploy script). Streams agent
   steps via SSE from FastAPI. No throwaway phase — there's no free-tier-deploy constraint to
   dodge since we already have a VPS, so Gradio would just be extra work to replace later.

2. **Scaffold everything now vs. Phase 1 first, check in.**
   → Phase 1 first. Scaffolded the skeleton (this commit) but only Phase 1 (F1 shared state/config
   + F2 ingestion/Qdrant) gets built out with real logic before the next check-in. Reason: can't
   validate agents/graph work until ingestion + Gemini + Qdrant are confirmed working end to end,
   and no point writing 4 agent stubs against an untested foundation.

3. **Caddy pattern + domain.**
   → Reuse the existing convention documented for this VPS (see `~/infra/Caddyfile`, one block
   per app — not caddy-docker-proxy, not per-project Caddyfile imports). Domain `froton.uz` is
   already on this VPS with a working Cloudflare wildcard cert, **single subdomain level only**
   (`thing.froton.uz`, not `api.thing.froton.uz` — two-level subs fail TLS on this cert, learned
   the hard way on tezyodla). Planned subdomains:
   - `analyst.froton.uz` → frontend (static Vue build, Caddy `file_server` + SPA fallback)
   - `analyst-api.froton.uz` → backend (FastAPI in Docker, `reverse_proxy analyst-api:8000`)

## Infra decisions

**Important correction (found 2026-07-29 while testing F2):** LLM/embedding access is NOT a
native Google AI Studio key — it's a class-wide **LiteLLM proxy** at
`https://saidazam-litellm-proxy.hf.space/v1` (OpenAI-compatible). The `sk-...` keys distributed
to the class are proxy keys, not Google keys; calling Google's endpoint directly with one fails
with `API key not valid`. Confirmed by inspecting the sibling `agentic-rag-api` app's
`llm.py`/`vectorstore.py` on the VPS (the prior, simpler course project — see below), which
already solved this. Client code goes through `langchain-openai` (`ChatOpenAI`/`OpenAIEmbeddings`
with `base_url=proxy_base_url`), never `langchain-google-genai`. Model names: `gemini-flash-lite`
(generation), `gemini-flash` (supervisor/critic — **some class keys 403 on this one**,
`key_model_access_denied`, fall back to flash-lite if so), `gemini-embedding` (embeddings). See
`backend/app/llm.py`.

| Piece | Choice | Why |
|---|---|---|
| LLM + embeddings | Class LiteLLM proxy (OpenAI-compatible), model names above | per-student key, free, but NOT a native Gemini key — see correction above |
| Vector DB | Qdrant, own Docker container (not embedded) | persists across restarts, matches "one container per project" VPS convention |
| SQL | SQLite (`data/company.db`) | zero extra infra, read-only guard in code |
| Code agent sandbox | Python subprocess with timeout/resource cap inside the backend container | container itself is the sandbox boundary; no nested Docker-in-Docker needed for a course project |
| Web search | Tavily | free tier, optional — skip gracefully with no key |
| Tracing | Langfuse **Cloud** (free tier), not self-hosted | self-hosted needs Postgres+ClickHouse+Redis, too heavy to share this box with 4 other live apps |
| Frontend | Vue 3 + Vite | reuse existing skill/deploy pattern from tezyodla |
| Deploy | Docker Compose, one stack for this project (`backend`, `qdrant` on the internal `web` network, no published ports), Caddy reverse-proxies both public subdomains | matches every other app already on this VPS |

## Build order (from the guide, unchanged)

- **Phase 1 — Foundation**: F1 shared state/config, F2 ingestion + Qdrant. ← **current phase**
- **Phase 2 — Specialist agents**: F3 retriever, F4 web, F5 text-to-SQL, F6 code exec. Build + test each alone.
- **Phase 3 — Orchestration**: F7 supervisor/router, F8 critic, F9 LangGraph wiring.
- **Phase 4 — Memory & eval**: F10 long-term memory, F11 RAGAS + LLM-judge harness.
- **Phase 5 — Ship**: F12 Langfuse tracing, F13 Vue streaming frontend, F14 deploy to froton VPS.

## Repo layout

```
multi-agent-analyst/
├── backend/
│   ├── app/
│   │   ├── config.py       — env/config loading
│   │   ├── state.py        — AgentState TypedDict
│   │   ├── ingestion.py     — load/chunk/embed/store (F2)
│   │   ├── agents/          — retriever.py, web.py, data_sql.py, code_exec.py (F3-6)
│   │   ├── graph.py         — LangGraph wiring (F9)
│   │   ├── memory.py        — long-term memory (F10)
│   │   └── main.py          — FastAPI app + SSE streaming endpoint
│   ├── eval/                — RAGAS + LLM-judge harness (F11)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                — Vue 3 + Vite (F13)
├── data/                    — company.db (SQLite), sample docs for ingestion
├── docs/
│   └── PLAN.md              — this file
├── docker-compose.yml
└── .env.example
```

## Future considerations (not now — noted for later)

- User wants to eventually replace/supplement Tavily with a self-built scraper and/or 2-3
  ready scraping frameworks, for efficiency — driven by a plan to connect this multi-agent
  system to the froton.uz portfolio and/or tezyodla project later, not just this course capstone.
  Revisit once F4 (web agent) is done and the course submission is safe; don't build this now,
  it's explicitly deferred.

## Status

- [x] Repo skeleton created (2026-07-29)
- [x] F1: config.py + state.py
- [x] F2: ingestion.py + Qdrant wired (Qdrant Cloud for local dev, self-hosted container
      planned for VPS), tested end-to-end with the class proxy key (2026-07-29) — ingested
      a sample doc, similarity search returned the correct chunk
- [x] F3 retriever agent — tested alone, returns correct chunk
- [x] F4 web agent — tested alone with Tavily key (4 live results) and without key (skips gracefully)
- [x] F5 text-to-SQL agent — `data/seed_db.py` creates a synthetic `company.db` matching the
      sample doc's narrative; tested "how many starter customers churned in Q3" → correct answer
      (4); read-only enforced two ways: SELECT-prefix guard in code AND SQLite opened via
      `mode=ro` URI (verified an INSERT actually raises `OperationalError`, not just refused by
      the code-level check)
- [x] F6 code-exec agent — subprocess + 10s timeout is the sandbox boundary (matches the guide's
      minimum bar, no nested Docker-in-Docker); tested correct math AND confirmed the timeout
      actually kills a runaway `while True` script
- [x] F7 supervisor — routes correctly by question type (retriever for "why"/narrative,
      data for counts/aggregates, web for general knowledge, code for pure calculation,
      finish when evidence already gathered). Needed few-shot examples in the prompt —
      abstract rules alone weren't reliable on `gemini-flash-lite` (this key has no
      `gemini-flash` access, see llm.py)
- [x] F8 critic — approves a correct/supported answer, catches and flags a fabricated one
      with a specific reason (tested with a deliberately wrong answer citing facts not in
      evidence)
- [x] F9 graph wiring — full LangGraph compiled and run end-to-end on a two-part question
      ("why did churn rise, and how many customers churned" → retriever → data → generate
      → critic(ok), single pass, no revision needed); `recursion_limit=25` set on invoke
      as the hard termination guarantee
- [x] F10 long-term memory — separate Qdrant collection `analyst_memory` (`backend/app/memory.py`);
      `graph.run()` recalls similar past turns and prepends them to the question before the
      supervisor sees it, then stores the (original question, answer) pair after. Tested: asked
      "how many starter customers churned in Q3?" (4), then the bare follow-up "and how many in
      Q2?" — correctly resolved to "starter customers churned in Q2" (3), matching seed data
- [x] F11 eval harness — `backend/eval/` (dataset.py: 11 questions spanning all 4 agent
      types; run_eval.py: RAGAS faithfulness+answer_relevancy + custom LLM-judge 1-5).
      Needed a compatibility shim (`_ragas_compat.py`) for a real ragas/langchain-community
      version incompatibility — see memory. First full run surfaced 3 real bugs, all fixed:
      1. Supervisor could loop calling the SAME agent forever (hit LangGraph's hard
         `recursion_limit` and crashed) → added a step-budget circuit breaker
         (`MAX_SUPERVISOR_CALLS=5`) AND a deterministic guard against re-picking an agent
         that already produced a result.
      2. With memory recall enabled, supervisor sometimes picked 'finish' on the very
         first call with zero evidence gathered (latched onto memory-recalled text as if
         it were evidence) → added `RouteMustPick` schema (no 'finish' option) for the
         first supervisor call of a turn, and gave `graph.run()` a `use_memory=False` mode
         so eval runs are cold/reproducible instead of shortcut by prior eval runs.
      3. A "how many people on the support team" question got routed to the SQL agent
         (superficial 'how many' match) even though headcount isn't in the DB schema —
         data agent returned an irrelevant count, critic wrongly approved the resulting
         "evidence doesn't cover this" non-answer as ok (its criteria was hallucination-only,
         not relevance). Fixed: critic now also fails non-answers, and `RouteMustPick`
         extended to apply right after a revise too (previously the model just re-picked
         'finish' immediately, defeating the point of revising), with a same-agent-repeat
         fallback to the other most-plausible source (data<->retriever).
      Final clean run (memory cleared, `use_memory=False`): **LLM-judge 4.91/5 avg over 11
      questions**, **RAGAS faithfulness 1.0, answer_relevancy 0.886**. Good material for the
      guide's required "error analysis" section later — these 3 are real, traceable failures
      with a fix each, exactly the format asked for.
- [x] F12 Langfuse tracing — installed the official `langfuse/skills` repo skill
      (`C:\Users\User\.claude\skills\langfuse\`) and followed its instrumentation +
      self-audit workflow properly (fetch real traces via `langfuse-cli`, audit against
      the fetched-fresh best-practices page, fix gaps, re-audit). Real user key added
      2026-07-30. `backend/app/tracing.py`: `traced_llm()` helper wraps every LLM call in
      a manually-typed Langfuse span; `graph.py`'s `run()`/`stream()` wrap the whole
      request in `propagate_attributes()` (trace name/session_id/tags/environment) +
      a root span whose input/output are the clean question/answer (not raw state).
      Nodes typed per the multi-agent guidance: supervisor/retriever/web/data/code as
      `agent`, critic as `evaluator` (+ a `critic-verdict` BOOLEAN score per turn), generate
      as `chain`. `session_id` threaded from frontend (one per page load, groups a visit
      into one Langfuse session) through `/ask` and `/ask/stream` down to the trace.
      Eval harness tags its traces `["eval"]` / `environment="development"` so they don't
      pollute production dashboards. Real bugs found via the audit loop, all fixed:
      1. **Duplicate spans**: passing the LangChain `CallbackHandler` at the graph-level
         `invoke()`/`stream()` config made LangGraph auto-trace every node as a generic
         `CHAIN`, while my own `@observe()` decorators added a SECOND nested span for the
         same node — the exact "duplicate dispatch + execution" anti-pattern the guide
         warns about (48 observations for one request). Fixed by dropping the graph-level
         callback entirely and attaching tracing only at each individual LLM call site —
         down to a clean ~17 observations, correctly nested, no duplication.
      2. **Context lost across threads (streaming only)**: `/ask/stream`'s SSE generator,
         when drained by Starlette's threadpool (`iterate_in_threadpool`), can have each
         `next()` call serviced by a *different* thread — and Python contextvars (which
         Langfuse's OTEL-based span tracking relies on) don't cross threads. Confirmed via
         a real trace where the `critic` span came out as its own top-level trace instead
         of nesting under `analyst-query`, and independently reproduced the exact mechanism
         with a minimal contextvars+ThreadPoolExecutor test. Fixed: `main.py`'s
         `ask_stream()` now runs the entire `stream()` generator to completion inside one
         dedicated worker thread that pushes plain dicts into a `queue.Queue`; the actual
         SSE-yielding generator Starlette drains never touches Langfuse context, so it
         doesn't matter which thread services it. The blocking `/ask` endpoint never had
         this problem (one synchronous call, one thread throughout).
      3. **Model name / token usage not captured**: `GENERATION` observations showed
         `model=None, usage=None` despite the raw LangChain response clearly having both
         (`response_metadata['model_name']`, `response_metadata['token_usage']` — verified
         directly). Isolated testing (a minimal `start_as_current_observation` + plain
         `.invoke()`, no LangGraph involved) reproduced the same gap, and checking the SDK
         source confirmed the extraction code path *should* work — this matches several
         open upstream GitHub issues (langfuse/langfuse #8025, #9159, #13075) describing
         the same symptom with ChatOpenAI + CallbackHandler. Worked around by having
         `traced_llm()` manually extract `model_name`/`token_usage` from the response and
         attach them via `gen.update(model=..., usage_details=...)` — call it fixed at the
         "data is captured in Langfuse's input/output" level; `cost`/`usageDetails` still
         show empty in the API even with this manual attempt, which points to a deeper
         SDK/ingestion-side gap for this exact langfuse 4.14.1 + langchain 1.3.x
         combination. Documented rather than chased further — everything else (hierarchy,
         naming, session/environment/tags, scores, clean input/output, no duplication)
         fully meets the best-practices checklist.
      Also found and fixed two supervisor-quality regressions while auditing real traces
      (not directly tracing-related, but surfaced by looking at real production traces):
      a "what is 42?" follow-up (memory-recalled trivia, not a calculation) was wrongly
      routed to `code` then `retriever` on fallback — fixed the `code` fallback to `web`
      and added an explicit few-shot example distinguishing "explain a number" from
      "compute with numbers". That fix's added prompt text then caused a *different*
      regression (a genuine "what is LangGraph used for" question started routing to
      `retriever` instead of `web`) — fixed by scoping the "needs an explanation ->
      retriever" rule explicitly to the user's own documents, re-verified both cases
      correct across repeated runs after the fix.
- [x] F13 frontend — Vue 3 + Vite in `frontend/`, `/ask/stream` SSE endpoint added to
      `backend/app/main.py` (+ non-streaming `/ask`), refactored `graph.py` to share a
      `stream()` generator with `run()` so memory/tracing behave identically either way.
      Verified live in-browser: typed a question, watched the trace stream node-by-node
      (supervisor->agent->generate->critic), correct final answer + evidence shown. Tested
      both a pure-code question and a memory-assisted multi-hop question.
      **Redesigned 2026-07-30** after user feedback ("white text on white in live trace",
      wanted it more professional): rebuilt the trace panel as a proper connected timeline
      (colored dot + label + detail per step, fade-in on arrival) instead of a flat list of
      colored boxes, and moved to a CSS-custom-property theming system (`--bg`, `--ink`,
      `--primary`, etc., light values in `:root` + dark overrides in
      `@media (prefers-color-scheme: dark)`). Two real bugs found fixing this:
      1. The dark-mode media query only touched a few selectors (`.page`, `.sub`, inputs) —
         never touched `.trace li`'s per-kind background colors, so dark mode kept the
         *light* backgrounds with light-on-light text on top. Root cause of the reported bug.
      2. My first rewrite put the `:root { --bg: ...; }` variable definitions inside
         `<style scoped>` — which doesn't work: Vue's scoped-CSS compiler appends a
         `[data-v-hash]` attribute selector to every rule, including `:root`, but `<html>`
         never receives that attribute (only elements the component renders do), so
         `:root[data-v-hash]` matches nothing and every variable silently fails to apply.
         Confirmed via `getComputedStyle` showing the variables resolving to a *different*
         leftover Vite scaffold stylesheet's own `:root` values instead (a `frontend/src/
         style.css` full of unused hero/next-steps boilerplate CSS from `npm create vite`
         that was never cleaned up). Fixed by moving the theme tokens into that file
         (rewritten to just tokens + a minimal reset) — `:root` must be genuinely global,
         it can't be scoped by a single component.
      Verified via `getComputedStyle` in both color schemes post-fix (dark: e.g. supervisor
      label `rgb(139,163,245)` on `rgb(28,32,36)` panel bg — correct token values, good
      contrast; light: page bg/ink resolve to the intended `#faf9f6`/`#1a1f1c`).
- [x] F14 backend deploy — `~/apps/analyst-api/` on the VPS: `docker-compose.yml` (qdrant +
      backend, both on the `web` network, resource-limited, no published ports, matching
      VPS convention), `.env` copied and re-pointed to the self-hosted qdrant container
      (`QDRANT_URL=http://qdrant:6333`, cleared `QDRANT_API_KEY` — dev used Qdrant Cloud,
      prod uses self-hosted, per the original plan). Built and started successfully.
      Verified internally (via `docker run --network web curlimages/curl`, no public
      exposure yet): `/health` ok, code-agent math question correct, SQL-agent question
      correct (company.db mounted via `./data:/app/data`), retriever-agent question correct
      (ingested the sample doc into the fresh self-hosted Qdrant first). Frontend production
      build (`VITE_API_BASE=https://analyst-api.froton.uz` baked in) staged at
      `~/apps/analyst-web/dist/` on the VPS, not yet served.
      **Live as of 2026-07-30**: DNS A records added via Cloudflare API (proxied, matching
      convention), Caddy blocks added to `~/infra/Caddyfile` (backed up first), bind mount
      for `~/apps/analyst-web/dist` added to `~/infra/docker-compose.yml` (backed up first).
      `docker compose up -d --force-recreate caddy` run with user confirmation (this
      recreates the ONE shared reverse proxy for every app on the box — brief interruption
      to all of them, not just this one). Verified: all other containers (lifeos-bot,
      tezyodla-api, uzbstats-api, froton-api/db) stayed up the whole time, both new certs
      issued automatically within ~15s, and a real question through the public URL
      (`https://analyst-api.froton.uz/ask`) returned the correct answer.
      **Correction (2026-07-30)**: the `favicon.svg`/`icons.svg` files noted earlier as
      "orphaned, cause unknown" are NOT orphans — they're this project's own
      `frontend/public/` assets (favicon already wired up via `<link rel="icon">` in
      `index.html`; `icons.svg` is an unused leftover sprite sheet, harmless). Their
      surprising "2026-07-07" timestamp is just the `create-vite` npm template package's
      own bundled-file mtime, preserved through scaffolding — nothing to do with any prior
      session or activity on the VPS. Confirmed by checking the same files locally in
      `frontend/public/`, same timestamp.
      **Rate limit note (2026-07-30)**: the class LLM proxy key has a real per-window
      request quota (seen: "Current limit: 15, Remaining: 0" from `openai.RateLimitError`
      429). Heavy same-session testing (repeated eval runs, isolated debug scripts, routing
      regression tests) exhausted it once, causing the OpenAI SDK's built-in retry-with-
      backoff to silently stall a few requests for tens of seconds and one to fail outright
      with a dropped SSE connection — not a code bug, confirmed by retrying after the
      window reset and getting an immediate correct response. Worth remembering next time
      something "hangs" against this proxy: check for a 429 in `docker logs analyst-backend`
      before assuming it's a real bug.

## Phase 5 — DONE. All 14 features (F1-F14) built, tested, and deployed live at
`analyst.froton.uz` (frontend) / `analyst-api.froton.uz` (backend API).

## Follow-up idea (user, 2026-07-30): smarter Caddy reload
Recreating the single shared `caddy` container to pick up one new app's config briefly
interrupts every other live app on the box — user flagged this as bad practice worth
improving. Options to research: `caddy-docker-proxy` (dynamic per-container labels, no
central Caddyfile edit needed at all), or hitting Caddy's admin API (`POST /load` on
`localhost:2019`) to push a new config live without a container restart, which would also
sidestep the file-mount inode-swap gotcha entirely. Not urgent, revisit in a few days.
