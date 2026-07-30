import contextlib
import uuid

from langgraph.graph import END, StateGraph

from .agents.code_exec import code_agent
from .agents.data_sql import data_agent
from .agents.retriever import retriever_agent
from .agents.web import web_agent
from .critic import critic, route_after_critic
from .generate import generate_agent
from .memory import recall, remember_turn
from .state import AgentState
from .supervisor import supervisor
from .tracing import get_langfuse, tracing_enabled

RECURSION_LIMIT = 25  # hard cap so a mis-routing loop can never run forever


def build_graph():
    g = StateGraph(AgentState)

    g.add_node("supervisor", supervisor)
    g.add_node("retriever", retriever_agent)
    g.add_node("web", web_agent)
    g.add_node("data", data_agent)
    g.add_node("code", code_agent)
    g.add_node("generate", generate_agent)
    g.add_node("critic", critic)

    g.set_entry_point("supervisor")

    g.add_conditional_edges(
        "supervisor",
        lambda s: s["plan"],
        {
            "retriever": "retriever",
            "web": "web",
            "data": "data",
            "code": "code",
            "finish": "generate",
        },
    )
    for agent_name in ("retriever", "web", "data", "code"):
        g.add_edge(agent_name, "supervisor")

    g.add_edge("generate", "critic")
    g.add_conditional_edges("critic", route_after_critic, {"finish": END, "revise": "supervisor"})

    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def _build_initial_state(question: str, use_memory: bool) -> AgentState:
    augmented_question = question
    if use_memory:
        past_turns = recall(question)
        if past_turns:
            context = "\n\n".join(past_turns)
            augmented_question = (
                f"Relevant earlier conversation:\n{context}\n\nCurrent question: {question}"
            )
    return {
        "question": augmented_question,
        "plan": "",
        "documents": [],
        "sql_result": None,
        "code_result": None,
        "answer": "",
        "steps": [],
        "revisions": 0,
    }


def _trace_contexts(question: str, session_id: str | None, tags: list[str] | None, environment: str):
    """Returns (attrs_ctx, span_ctx) — real Langfuse context managers if tracing is
    configured, or no-ops otherwise, so callers don't need an if/else around every
    invocation. propagate_attributes sets trace-level session/tags/environment (must be
    set at creation time, can't be added after the fact); the span is the root
    observation whose input/output show up as the trace's own input/output."""
    if not tracing_enabled():
        return contextlib.nullcontext(), contextlib.nullcontext()

    from langfuse import propagate_attributes

    attrs_ctx = propagate_attributes(
        trace_name="analyst-query",
        session_id=session_id or str(uuid.uuid4()),
        tags=tags,
        environment=environment,
    )
    span_ctx = get_langfuse().start_as_current_observation(
        as_type="span", name="analyst-query", input=question
    )
    return attrs_ctx, span_ctx


def run(
    question: str,
    use_memory: bool = True,
    session_id: str | None = None,
    tags: list[str] | None = None,
    environment: str = "production",
) -> AgentState:
    # use_memory=False for the eval harness: fixed questions must be scored cold, not
    # increasingly shortcut by memory of earlier eval runs of the same question set
    initial_state = _build_initial_state(question, use_memory)
    # NOT passing callbacks here on purpose — see comment on _trace_contexts. Each node
    # attaches the Langfuse callback itself, only around its own LLM call, so it nests
    # under that node's own @observe span instead of LangGraph auto-creating a second,
    # redundant top-level span per node.
    invoke_config = {"recursion_limit": RECURSION_LIMIT}

    attrs_ctx, span_ctx = _trace_contexts(question, session_id, tags, environment)
    with attrs_ctx, span_ctx as root:
        result = get_graph().invoke(initial_state, config=invoke_config)
        if tracing_enabled():
            root.update(output=result["answer"])
            get_langfuse().set_current_trace_io(input=question, output=result["answer"])

    if use_memory:
        remember_turn(question, result["answer"])  # store the original question, not the augmented one
    return result


def stream(
    question: str,
    use_memory: bool = True,
    session_id: str | None = None,
    tags: list[str] | None = None,
    environment: str = "production",
):
    """Yields (node_name, node_output_dict) as each graph step completes — for a live
    frontend trace (F13). Same memory/tracing behavior as run(), just not blocking."""
    initial_state = _build_initial_state(question, use_memory)
    invoke_config = {"recursion_limit": RECURSION_LIMIT}
    final_answer = None

    attrs_ctx, span_ctx = _trace_contexts(question, session_id, tags, environment)
    with attrs_ctx, span_ctx as root:
        for update in get_graph().stream(initial_state, config=invoke_config):
            for node_name, node_output in update.items():
                if node_name == "generate":
                    final_answer = node_output.get("answer")
                yield node_name, node_output

        if tracing_enabled() and final_answer:
            root.update(output=final_answer)
            get_langfuse().set_current_trace_io(input=question, output=final_answer)

    if use_memory and final_answer:
        remember_turn(question, final_answer)
