from typing import Literal

from langfuse import observe
from pydantic import BaseModel, Field

from .llm import get_llm_flash
from .state import AgentState
from .tracing import get_langfuse, traced_llm, tracing_enabled


class Route(BaseModel):
    next: Literal["retriever", "web", "data", "code", "finish"] = Field(
        description="Which agent should run next, or 'finish' if enough evidence is gathered."
    )


class RouteMustPick(BaseModel):
    """Same as Route but without 'finish' — used for the first call of a turn so the
    model can't skip straight to an answer with zero evidence gathered. Seen in practice:
    with a memory-augmented question that reads like it already contains an answer (from
    an earlier turn's recalled context), flash-lite picked 'finish' immediately despite the
    prompt explicitly stating 'Documents gathered: 0' — a real instruction-following gap,
    not something to just re-prompt around."""

    next: Literal["retriever", "web", "data", "code"] = Field(
        description="Which agent should run next. At least one real agent must run before finishing."
    )


MAX_SUPERVISOR_CALLS = 5  # circuit breaker — a mis-routing loop must terminate gracefully,
# not hit LangGraph's hard recursion_limit and crash the whole request

# Deterministic guard against the observed failure mode: the LLM router re-picking the
# SAME agent repeatedly even after it already returned a result (seen with flash-lite on
# "what drove Enterprise revenue growth" — called retriever 5x instead of stopping once
# it had a matching document). Prompt instructions alone weren't reliable enough on this
# model, so don't trust it for this specific check.
_HAS_RESULT = {
    "retriever": lambda s: len(s["documents"]) > 0,
    "web": lambda s: len(s["documents"]) > 0,
    "data": lambda s: s["sql_result"] is not None,
    "code": lambda s: s["code_result"] is not None,
}


def _last_agent_step(steps: list[str]) -> str | None:
    for step in reversed(steps):
        name = step.split("(")[0]
        if name in _HAS_RESULT:
            return name
    return None


# When the critic sends us back with "revise", picking 'finish' again immediately is a
# no-op that defeats the whole point of revising (observed in practice — the model did
# exactly this rather than trying a different source). If it then also repeats the same
# already-insufficient agent, fall back to the most plausible alternate source instead of
# forcing 'finish' — data vs retriever is the actual confusion seen (a count question
# whose real answer lives in prose, or vice versa). code -> web (not retriever): seen in
# practice on "what is 42?" (a memory-recalled trivia/definitional question, not a real
# calculation) — code correctly failed to "define" 42, and retriever would be useless too
# since the company docs have nothing to do with it; web is the only agent that can
# actually look up what something general-knowledge means.
_FALLBACK_AGENT = {
    "data": "retriever",
    "retriever": "data",
    "web": "retriever",
    "code": "web",
}


@observe(as_type="agent", name="supervisor")
def supervisor(state: AgentState) -> dict:
    calls_so_far = sum(1 for s in state["steps"] if s.startswith("supervisor->"))
    if calls_so_far >= MAX_SUPERVISOR_CALLS:
        next_agent = "finish(step budget reached)"
        if tracing_enabled():
            get_langfuse().update_current_span(
                input={"question": state["question"], "steps_so_far": state["steps"]},
                output={"next": next_agent},
            )
        return {
            "plan": "finish",
            "steps": state["steps"] + [f"supervisor->{next_agent}"],
        }

    last_step = state["steps"][-1] if state["steps"] else ""
    must_pick = calls_so_far == 0 or last_step.startswith("critic(revise")

    route_schema = RouteMustPick if must_pick else Route
    decision = traced_llm(
        "supervisor-route",
        get_llm_flash(),
        (
            f"Question: {state['question']}\n"
            f"Steps taken so far: {state['steps']}\n"
            f"Documents gathered: {len(state['documents'])}\n"
            f"SQL result: {state['sql_result']}\n"
            f"Code result: {state['code_result']}\n\n"
            "Decide the next agent to call, or 'finish' if there's already enough evidence "
            "above to answer.\n\n"
            "Examples:\n"
            "Q: 'why did customers cancel last quarter?' -> retriever (the REASON lives in "
            "written notes/docs, not the database — a SQL table has no 'reason' column)\n"
            "Q: 'how many customers churned in Q3?' -> data (a COUNT, exists as rows in the "
            "SQL database)\n"
            "Q: 'what percent of starter customers are active?' -> data (an aggregate over "
            "structured records)\n"
            "Q: 'what's the latest LangGraph version?' -> web (general/current info, not in "
            "the user's own documents or database)\n"
            "Q: 'what is 45 * 12?' -> code (pure calculation FROM given numbers, no lookup "
            "needed)\n"
            "Q: 'what is 42?' or 'what does 42 mean?' -> web (this ASKS WHAT A NUMBER MEANS "
            "— trivia/definition, not a calculation. code can only compute an answer from "
            "numbers already in the question; it can't look up what something refers to. "
            "Don't route a bare number or a past answer mentioned in earlier conversation "
            "to code just because it looks numeric.)\n\n"
            "Key test: 'requires an explanation' is NOT by itself a reason to pick "
            "retriever — retriever ONLY searches the user's own uploaded documents/notes "
            "about their own company/business. If the explanation needed is about the "
            "user's own company (why something happened, what a policy/process was), use "
            "retriever. If it's general/external knowledge (what a tool does, what a term "
            "or number means, current events), use web instead, even though that's also "
            "'an explanation'. Only use data when the answer is literally a count/aggregate/"
            "row lookup from the database. Only use code when the question gives you "
            "numbers to compute WITH, not a number to explain.\n\n"
            "If Documents gathered > 0 or SQL/code result is already set and it plausibly "
            "answers the question, choose 'finish' — don't call the same agent twice on the "
            "same question."
        ),
        structured_schema=route_schema,
    )

    next_agent = decision.next
    last_agent = _last_agent_step(state["steps"])
    if next_agent == last_agent and _HAS_RESULT[last_agent](state):
        if must_pick:
            next_agent = _FALLBACK_AGENT[last_agent]
        else:
            # model tried to repeat an agent that already produced a result — force
            # finish instead of trusting it to eventually stop on its own
            next_agent = "finish"

    if tracing_enabled():
        get_langfuse().update_current_span(
            input={"question": state["question"], "steps_so_far": state["steps"]},
            output={"next": next_agent},
        )

    return {
        "plan": next_agent,
        "steps": state["steps"] + [f"supervisor->{next_agent}"],
    }
