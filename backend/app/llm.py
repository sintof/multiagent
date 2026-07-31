"""
All model calls go through the class LiteLLM proxy (OpenAI-compatible), never directly
to Google. Model names per the class's routing rules:
  - gemini-flash-lite : high-volume calls (generation) AND supervisor/critic calls.
  - gemini-flash       : intended for supervisor/critic per the guide, but confirmed 403
                          ("key not allowed to access model") on this key — scoped to
                          ['flash-lite', 'gemini-flash-lite', 'gemini-embedding'] only.
                          get_llm_flash() below uses flash-lite until/unless access widens.
  - gemini-embedding   : embeddings for the vector store
"""

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from .config import settings

MODEL_LITE = "gemini-flash-lite"
MODEL_FLASH = "gemini-flash-lite"  # would be "gemini-flash" if this key had access
MODEL_EMBED = "gemini-embedding"


def get_llm_lite(temperature: float = 0.2) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=settings.proxy_base_url,
        api_key=settings.gemini_api_key,
        model=MODEL_LITE,
        temperature=temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )


def get_llm_flash(temperature: float = 0.0) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=settings.proxy_base_url,
        api_key=settings.gemini_api_key,
        model=MODEL_FLASH,
        temperature=temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )


def get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        base_url=settings.proxy_base_url,
        api_key=settings.gemini_api_key,
        model=MODEL_EMBED,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
