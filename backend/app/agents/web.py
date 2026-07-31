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
    try:
        results = client.search(
            state["question"], max_results=4, timeout=settings.web_search_timeout_seconds
        )["results"]
    except Exception as exc:
        # Tavily/network failure shouldn't hang or crash the whole graph run — surface
        # it as a step with zero documents so the supervisor/critic can react (retry a
        # different agent, or finish with a best-effort answer) instead of the request
        # dying silently.
        if tracing_enabled():
            get_langfuse().update_current_span(
                input=state["question"], output=f"web search failed: {exc}"
            )
        return {"steps": state["steps"] + [f"web(error: {exc})"]}

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
