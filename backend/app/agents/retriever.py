from langfuse import observe

from ..ingestion import get_vectorstore
from ..state import AgentState
from ..tracing import get_langfuse, tracing_enabled


@observe(as_type="agent", name="retriever-agent")
def retriever_agent(state: AgentState) -> dict:
    docs = get_vectorstore().similarity_search(state["question"], k=4)
    chunks = [d.page_content for d in docs]

    if tracing_enabled():
        get_langfuse().update_current_span(
            input=state["question"],
            output=f"{len(chunks)} chunk(s) retrieved" if chunks else "no matching chunks",
        )

    return {
        "documents": state["documents"] + chunks,
        "steps": state["steps"] + ["retriever"],
    }
