# Multi-Agent AI Analyst

LangGraph supervisor system: router → {retriever, web, text-to-SQL, code exec} → critic, with
memory, RAGAS/LLM-judge eval, Langfuse tracing, deployed on the froton VPS.

Live at [analyst.froton.uz](https://analyst.froton.uz) (frontend) /
[analyst-api.froton.uz](https://analyst-api.froton.uz) (backend API).

See [`docs/PLAN.md`](docs/PLAN.md) for the architecture decisions, build order, and every bug
found/fixed along the way, and [`docs/rubric-source.html`](docs/rubric-source.html) for the
original course guide/rubric.

## Local setup

1. Copy `.env.example` to `.env` and fill in `GEMINI_API_KEY` (the class LiteLLM proxy key —
   see `docs/PLAN.md` for why this isn't a native Google AI Studio key).
2. `docker compose up -d qdrant` (or point `QDRANT_URL`/`QDRANT_API_KEY` at Qdrant Cloud's free
   tier for local dev without Docker)
3. `pip install -r backend/requirements.txt`
4. `python data/seed_db.py` to generate the SQLite database for the text-to-SQL agent
5. `PYTHONPATH=backend uvicorn app.main:app --reload` from the repo root

## Evaluation

`PYTHONPATH=backend python -m eval.run_eval` from the repo root runs the fixed 11-question set
through the full graph and reports RAGAS (faithfulness, answer_relevancy) + LLM-judge scores.

## Status

All 14 features (F1-F14) built, tested, and deployed — see `docs/PLAN.md` for full detail.
