from langfuse import observe

from .llm import get_llm_lite
from .state import AgentState
from .tracing import get_langfuse, traced_llm, tracing_enabled


def _collect_evidence(state: AgentState) -> str:
    evidence = "\n\n".join(state["documents"])
    if state.get("sql_result"):
        evidence += f"\n\nSQL evidence:\n{state['sql_result']}"
    if state.get("code_result"):
        evidence += f"\n\nCode evidence:\n{state['code_result']}"
    return evidence or "(no evidence gathered)"


@observe(as_type="chain", name="generate")
def generate_agent(state: AgentState) -> dict:
    evidence = _collect_evidence(state)
    answer = traced_llm(
        "generate-answer",
        get_llm_lite(temperature=0.2),
        f"Question: {state['question']}\n\nEvidence:\n{evidence}\n\n"
        "Answer the question using ONLY the evidence above. If the evidence doesn't "
        "support an answer, say so honestly instead of guessing.",
    ).content

    if tracing_enabled():
        get_langfuse().update_current_span(
            input={"question": state["question"], "evidence": evidence},
            output=answer,
        )

    return {"answer": answer, "steps": state["steps"] + ["generate"]}
