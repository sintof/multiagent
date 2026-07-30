import json
import queue
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .graph import run, stream

app = FastAPI(title="Multi-Agent AI Analyst")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str
    session_id: str | None = None  # frontend generates one per page load, groups a
    # visitor's questions into one Langfuse session — same recalled-memory semantics


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
def ask(req: AskRequest):
    result = run(req.question, session_id=req.session_id)
    return {
        "answer": result["answer"],
        "steps": result["steps"],
        "documents": result["documents"],
        "sql_result": result["sql_result"],
        "code_result": result["code_result"],
    }


@app.post("/ask/stream")
def ask_stream(req: AskRequest):
    # stream()'s Langfuse span context is contextvar-based, and Starlette drains a sync
    # generator by calling next() via a threadpool — a different worker thread (and
    # therefore a blank contextvars snapshot) can service each individual next() call,
    # silently breaking span nesting partway through a request (confirmed: one real
    # request's "critic" span came out as its own top-level trace instead of nesting
    # under "analyst-query"). Running the whole graph iteration to completion in one
    # dedicated thread keeps the context consistent throughout; the queue is the only
    # thing crossing the thread boundary, and it carries plain dicts, not context.
    q: "queue.Queue" = queue.Queue()
    DONE = object()

    def worker():
        try:
            for node_name, node_output in stream(req.question, session_id=req.session_id):
                payload = {"node": node_name}
                for key in ("steps", "answer", "sql_result", "code_result"):
                    if key in node_output:
                        payload[key] = node_output[key]
                q.put(payload)
        finally:
            q.put(DONE)

    threading.Thread(target=worker, daemon=True).start()

    def event_gen():
        while True:
            payload = q.get()
            if payload is DONE:
                break
            yield f"data: {json.dumps(payload)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
