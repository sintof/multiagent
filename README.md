# Multi-Agent AI Analyst

LangGraph supervisor system: router → {retriever, web, text-to-SQL, code exec} → critic, with
memory, RAGAS/LLM-judge eval, Langfuse tracing, deployed on the froton VPS.

See [`docs/PLAN.md`](docs/PLAN.md) for the architecture decisions and build order, and
[`docs/rubric-source.html`](docs/rubric-source.html) for the original course guide/rubric.

## Local setup

1. Copy `.env.example` to `.env` and fill in `GEMINI_API_KEY` (get one free at
   aistudio.google.com/apikey — never commit this file).
2. `docker compose up -d qdrant`
3. `pip install -r backend/requirements.txt` (or run the backend in its own container too, once
   `Dockerfile` + `main.py` are filled in)

## Status

Phase 1 (shared state + ingestion) in progress — see `docs/PLAN.md` for what's done.
