from langfuse import observe
from tavily import TavilyClient

from ..config import settings
from ..state import AgentState
from ..tracing import get_langfuse, tracing_enabled


@observe(as_type="agent", name="web-agent")
def web_agent(state: AgentState) -> dict:
    if not settings.tavily_api_key:
        if tracing_enabled():
            get_langfuse().update_current_span(
                input=state["question"], output="skipped — no Tavily key configured"
            )
        return {"steps": state["steps"] + ["web(skipped, no key)"]}

    client = TavilyClient(api_key=settings.tavily_api_key)
    results = client.search(state["question"], max_results=4)["results"]
    contents = [r["content"] for r in results]

    if tracing_enabled():
        get_langfuse().update_current_span(
            input=state["question"],
            output=f"{len(contents)} result(s) from: " + ", ".join(r.get("url", "") for r in results),
        )

    return {
        "documents": state["documents"] + contents,
        "steps": state["steps"] + ["web"],
    }
