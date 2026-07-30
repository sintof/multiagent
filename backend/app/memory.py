from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from langchain_qdrant import QdrantVectorStore

from .config import settings
from .llm import get_embeddings

MEMORY_COLLECTION = "analyst_memory"

_memory_store: QdrantVectorStore | None = None


def get_memory_store() -> QdrantVectorStore:
    global _memory_store
    if _memory_store is None:
        client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
        embeddings = get_embeddings()
        if not client.collection_exists(MEMORY_COLLECTION):
            probe_dim = len(embeddings.embed_query("dimension probe"))
            client.create_collection(
                collection_name=MEMORY_COLLECTION,
                vectors_config=VectorParams(size=probe_dim, distance=Distance.COSINE),
            )
        _memory_store = QdrantVectorStore(
            client=client, collection_name=MEMORY_COLLECTION, embedding=embeddings
        )
    return _memory_store


def remember_turn(question: str, answer: str) -> None:
    get_memory_store().add_texts([f"Q: {question}\nA: {answer}"])


def recall(question: str, k: int = 3) -> list[str]:
    docs = get_memory_store().similarity_search(question, k=k)
    return [d.page_content for d in docs]
