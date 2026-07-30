from pathlib import Path

from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from .config import settings
from .llm import get_embeddings


def get_vectorstore() -> QdrantVectorStore:
    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    embeddings = get_embeddings()
    if not client.collection_exists(settings.qdrant_collection):
        # embedding dimension varies by model/provider — probe it instead of hardcoding
        probe_dim = len(embeddings.embed_query("dimension probe"))
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=probe_dim, distance=Distance.COSINE),
        )
    return QdrantVectorStore(
        client=client,
        collection_name=settings.qdrant_collection,
        embedding=embeddings,
    )


def ingest_file(path: str) -> int:
    docs = TextLoader(path, encoding="utf-8").load()
    chunks = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=150
    ).split_documents(docs)
    get_vectorstore().add_documents(chunks)
    return len(chunks)


def ingest_dir(dir_path: str) -> int:
    total = 0
    for path in Path(dir_path).glob("**/*.txt"):
        total += ingest_file(str(path))
    return total
