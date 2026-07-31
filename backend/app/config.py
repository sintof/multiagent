import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    gemini_api_key: str = os.environ["GEMINI_API_KEY"]
    # class LiteLLM proxy — OpenAI-compatible, routes to Gemini. Never call Google directly.
    proxy_base_url: str = os.getenv("PROXY_BASE_URL", "https://saidazam-litellm-proxy.hf.space/v1")
    qdrant_url: str = os.getenv("QDRANT_URL", "http://qdrant:6333")
    qdrant_api_key: str | None = os.getenv("QDRANT_API_KEY") or None  # "" (self-hosted, no auth) -> None
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "analyst_docs")
    sqlite_path: str = os.getenv("SQLITE_PATH", "data/company.db")

    tavily_api_key: str | None = os.getenv("TAVILY_API_KEY")
    langfuse_public_key: str | None = os.getenv("LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str | None = os.getenv("LANGFUSE_SECRET_KEY")
    langfuse_host: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    # Without an explicit timeout, langchain_openai falls through to the openai SDK's
    # default (600s per attempt, 2 retries -> ~30 min of silent hang on a slow/cold
    # proxy) before anything surfaces to the user. Every LLM/embedding call and the
    # Tavily web search go through these so a stalled upstream fails fast instead of
    # leaving the UI stuck on "Thinking" indefinitely.
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "1"))
    web_search_timeout_seconds: float = float(os.getenv("WEB_SEARCH_TIMEOUT_SECONDS", "20"))


settings = Settings()
