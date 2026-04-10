import os
import chromadb
from chromadb.utils import embedding_functions

from paths import CHROMA_DIR

# Ensure persistence directory exists
os.makedirs(CHROMA_DIR, exist_ok=True)

# Initialize local ChromaDB client (lightweight; no torch until embeddings run)
chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))

_embedding_fn = None
_collection = None


def _pick_device() -> str:
    import torch

    if torch.backends.mps.is_available():
        print("⚡ Vector Store: Hardware Acceleration (Mac MPS) Enabled!")
        return "mps"
    if torch.cuda.is_available():
        print("⚡ Vector Store: Hardware Acceleration (CUDA) Enabled!")
        return "cuda"
    print("⚙️ Vector Store: Running on Standard CPU.")
    return "cpu"


def _get_embedding_function():
    global _embedding_fn
    if _embedding_fn is None:
        try:
            import torch

            torch.set_num_threads(min(4, torch.get_num_threads()))
        except Exception:
            pass
        _embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2",
            device=_pick_device(),
        )
    return _embedding_fn


def _get_collection():
    global _collection
    if _collection is None:
        _collection = chroma_client.get_or_create_collection(
            name="financial_docs",
            embedding_function=_get_embedding_function(),
        )
    return _collection


class _LazyCollection:
    """Defer loading sentence-transformers until first Chroma use."""

    def __getattr__(self, name):
        return getattr(_get_collection(), name)


collection = _LazyCollection()


def delete_by_sources(sources: list[str]) -> None:
    """Remove all chunks whose metadata ``source`` matches (re-upload / replace)."""
    if not sources:
        return
    col = _get_collection()
    unique = list(dict.fromkeys(s for s in sources if s))
    if len(unique) == 1:
        col.delete(where={"source": unique[0]})
    else:
        col.delete(where={"$or": [{"source": s} for s in unique]})


def add_documents(ids: list[str], documents: list[str], metadatas: list[dict]) -> None:
    """
    Add batches of physical text chunks to ChromaDB.

    Args:
        ids (list[str]): Unique string identifiers for each chunk.
        documents (list[str]): The raw text content of the chunks.
        metadatas (list[dict]): The associated contextual metadata matrices.
    """
    _get_collection().add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )


def query_documents(query_texts: list[str], n_results: int = 5, where: dict = None) -> dict:
    """
    Retrieve the top-K semantically similar document chunks.

    Args:
        query_texts (list[str]): The input queries to search against.
        n_results (int): The maximum number of relevant contexts to return.
        where (dict): Optional constraints matching exactly to chroma's native syntaxes.

    Returns:
        dict: A structured dictionary response containing matching text and metadata.
    """
    params = {
        "query_texts": query_texts,
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        params["where"] = where

    return _get_collection().query(**params)
