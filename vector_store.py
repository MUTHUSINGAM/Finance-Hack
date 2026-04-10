import os
import chromadb
import torch
from chromadb.utils import embedding_functions

# Ensure persistence directory exists
os.makedirs("./chroma_db", exist_ok=True)

# Initialize local ChromaDB client
chroma_client = chromadb.PersistentClient(path="./chroma_db")

# Detect Hardware Acceleration
if torch.backends.mps.is_available():
    device = "mps"
    print("⚡ Vector Store: Hardware Acceleration (Mac MPS) Enabled!")
elif torch.cuda.is_available():
    device = "cuda"
    print("⚡ Vector Store: Hardware Acceleration (CUDA) Enabled!")
else:
    device = "cpu"
    print("⚙️ Vector Store: Running on Standard CPU.")

# Use local sentence-transformers mapped directly to hardware acceleration
sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2",
    device=device
)

collection = chroma_client.get_or_create_collection(
    name="financial_docs",
    embedding_function=sentence_transformer_ef
)

def add_documents(ids: list[str], documents: list[str], metadatas: list[dict]) -> None:
    """
    Add batches of physical text chunks to ChromaDB.
    
    Args:
        ids (list[str]): Unique string identifiers for each chunk.
        documents (list[str]): The raw text content of the chunks.
        metadatas (list[dict]): The associated contextual metadata matrices.
    """
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )

def query_documents(query_texts: list[str], n_results: int = 5) -> dict:
    """
    Retrieve the top-K semantically similar document chunks.
    
    Args:
        query_texts (list[str]): The input queries to search against.
        n_results (int): The maximum number of relevant contexts to return.
        
    Returns:
        dict: A structured dictionary response containing matching text and metadata.
    """
    return collection.query(
        query_texts=query_texts,
        n_results=n_results
    )
