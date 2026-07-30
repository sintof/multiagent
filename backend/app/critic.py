from langfuse import observe
from pydantic import BaseModel, Field

from .generate import _collect_evidence
from .llm import get_llm_flash
from .state import AgentState
from .tracing import get_langfuse, traced_llm, tracing_enabled

MAX_REVISIONS = 2


class Verdict(BaseModel):
    ok: bool = Field(description="True if the answer is correct AND fully supported by the evidence")
    reason: str = Field(description="One sentence explaining the verdict")


@observe(as_type="evaluator", name="critic")
def critic(state: AgentState) -> dict:
    evidence = _collect_evidence(state)
    verdict = traced_llm(
        "critic-verdict",
        get_llm_flash(),
        (
            f"Question: {state['question']}\n\nEvidence:\n{evidence}\n\n"
            f"Proposed answer: {state['answer']}\n\n"
            "Is this answer correct AND fully supported by the evidence above? Be strict on "
            "two counts:\n"
            "1. Hallucination: an answer that adds facts not present in the evidence is not "
            "supported.\n"
            "2. Non-answers: an answer that says the evidence is missing/insufficient/doesn't "
            "address the question is NOT ok, even though it's honest — it means the wrong "
            "evidence was gathered and a different source should be tried. Mark ok=False so "
            "the supervisor can retry with a different agent (e.g. the evidence gathered was "
            "a database count when the question actually needed the written notes, or vice "
            "versa)."
        ),
        structured_schema=Verdict,
    )
    revisions = state["revisions"] + (0 if verdict.ok else 1)
    # step budget: give up and return best-effort past MAX_REVISIONS, don't loop forever
    decision = "finish" if (verdict.ok or revisions >= MAX_REVISIONS) else "revise"

    if tracing_enabled():
        langfuse = get_langfuse()
        langfuse.update_current_span(
            input={"question": state["question"], "proposed_answer": state["answer"]},
            output={"ok": verdict.ok, "reason": verdict.reason},
        )
        # a same-turn LLM-as-judge verdict is exactly what Scores are for — lets the
        # dashboard filter/trend on critic pass rate independent of the trace tree
        langfuse.score_current_trace(
            name="critic-verdict",
            value=1 if verdict.ok else 0,
            data_type="BOOLEAN",
            comment=verdict.reason,
        )

    return {
        "revisions": revisions,
        "plan": decision,
        "steps": state["steps"] + [f"critic({'ok' if verdict.ok else 'revise: ' + verdict.reason})"],
    }


def route_after_critic(state: AgentState) -> str:
    return state["plan"]
