from langfuse import Langfuse, get_client

from .config import settings

_client: Langfuse | None = None


def tracing_enabled() -> bool:
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)


def _ensure_client() -> Langfuse:
    global _client
    if _client is None:
        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    return _client


def get_langfuse():
    """The active Langfuse client, for update_current_span/set_current_trace_io calls.
    Only call this after confirming tracing_enabled()."""
    _ensure_client()
    return get_client()


def traced_llm(node_name: str, llm, prompt: str, structured_schema=None):
    """Invoke an LLM, returning what llm.invoke() / llm.with_structured_output().invoke()
    normally would (an AIMessage, or a parsed schema instance).

    When tracing is enabled, wraps the call in a manually-built GENERATION span with
    model name + token usage read directly off the response object. NOT using
    Langfuse's LangChain CallbackHandler for this — confirmed by isolated testing that
    it doesn't extract model/usage for this setup (class LiteLLM proxy + langchain
    1.3.x + langfuse 4.14.1), even though the data is clearly present on the response's
    response_metadata/usage_metadata. Doing it manually here is more reliable than
    fighting that gap, and also drops the noisy RunnableSequence/RunnableLambda
    wrapper spans the callback added around with_structured_output() calls.
    """
    if not tracing_enabled():
        if structured_schema:
            return llm.with_structured_output(structured_schema).invoke(prompt)
        return llm.invoke(prompt)

    langfuse = get_langfuse()
    with langfuse.start_as_current_observation(as_type="generation", name=node_name) as gen:
        if structured_schema:
            result = llm.with_structured_output(structured_schema, include_raw=True).invoke(prompt)
            raw, parsed = result["raw"], result["parsed"]
        else:
            raw = llm.invoke(prompt)
            parsed = raw

        meta = getattr(raw, "response_metadata", {}) or {}
        usage = meta.get("token_usage") or {}
        usage_details = {
            key: value
            for key, value in {
                "input": usage.get("prompt_tokens"),
                "output": usage.get("completion_tokens"),
                "total": usage.get("total_tokens"),
            }.items()
            if value is not None
        }
        gen.update(
            model=meta.get("model_name"),
            input=prompt,
            output=getattr(raw, "content", str(raw)),
            usage_details=usage_details or None,
        )
        return parsed
