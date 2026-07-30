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


settings = Settings()
