from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
import os
import shutil
import threading
from pathlib import Path

from router import ask_question
from budget_manager import budget_manager, BUDGET_LIMIT
from paths import PDF_DIR

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifecycle context manager. Checks the local ChromaDB vectors
    at startup and automatically triggers bulk-vectorization if empty.
    """
    from vector_store import collection
    from ingestion import ingest_pdfs
    
    if collection.count() == 0:
        print("======================================================")
        print("Empty vector store detected!")
        sync = os.environ.get("SYNC_INGEST", "").strip().lower() in ("1", "true", "yes")
        if sync:
            print("SYNC_INGEST=1 — waiting until all PDFs are indexed...")
            print("======================================================")
            ingest_pdfs(pdf_dir=str(PDF_DIR), batch_size=256)
            print("Ingestion complete. Server is now ready.")
        else:
            print("Starting ingestion in the background — API will listen immediately.")
            print("RAG quality improves as batches finish; watch the console for progress.")
            print("For blocking startup: SYNC_INGEST=1. Faster extraction: PDF_SKIP_TABLES=1")
            print("======================================================")

            def _background_ingest() -> None:
                try:
                    ingest_pdfs(pdf_dir=str(PDF_DIR), batch_size=256)
                    print("Background PDF ingestion finished.")
                except Exception as e:
                    print(f"Background PDF ingestion failed: {e!r}")

            threading.Thread(
                target=_background_ingest, name="pdf-ingest", daemon=True
            ).start()
    else:
        print(f"Vector store loaded with {collection.count()} text chunks. Ready to serve.")
    yield

app = FastAPI(title="Finance Intelligence Portal API", lifespan=lifespan)

# Add CORS for the future frontend implementation
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    """Standardized schema for incoming user queries."""
    query: str
    selected_files: Optional[List[str]] = None

@app.get("/")
def health_check() -> Dict[str, Any]:
    """Basic health check and budget monitor endpoint."""
    return {"status": "Backend Active", "budget_used": budget_manager.spent}

@app.get("/api/budget")
def get_budget() -> Dict[str, Any]:
    """Retrieve the real-time API operational spending state."""
    return {
        "spent": budget_manager.spent, 
        "limit": BUDGET_LIMIT, 
        "circuit_breaker_active": not budget_manager.can_use_expensive_model()
    }

@app.get("/api/documents")
def get_documents() -> Dict[str, Any]:
    """Return PDF filenames under the project pdfs folder (same path used for ingestion)."""
    if not PDF_DIR.is_dir():
        return {"documents": []}
    files = [f for f in os.listdir(PDF_DIR) if f.lower().endswith(".pdf")]
    return {"documents": sorted(files)}

@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Dynamically pull physical buffers, bypass pool allocation manually, and vectorize live."""
    from pdf_extract import process_single_pdf
    from vector_store import add_documents, delete_by_sources

    pdf_dir = str(PDF_DIR)
    os.makedirs(pdf_dir, exist_ok=True)
    all_chunks = []

    for file in files:
        safe_name = Path(file.filename or "").name
        if not safe_name.lower().endswith(".pdf"):
            continue

        file_path = os.path.join(pdf_dir, safe_name)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Replace prior vectors for this filename (duplicate IDs would break Chroma add)
        delete_by_sources([safe_name])

        results = process_single_pdf((pdf_dir, safe_name))
        if results:
            all_chunks.extend(results)
            
    if all_chunks:
        for i in range(0, len(all_chunks), 256):
            batch = all_chunks[i:i + 256]
            ids = [item["id"] for item in batch]
            documents = [item["document"] for item in batch]
            metadatas = [item["metadata"] for item in batch]
            add_documents(ids, documents, metadatas)
            
    processed = len({Path(f.filename or "").name for f in files if Path(f.filename or "").name.lower().endswith(".pdf")})
    return {
        "message": f"Successfully vectorized {processed} file(s).",
        "chunks": len(all_chunks),
        "documents": sorted(
            n for n in os.listdir(PDF_DIR) if n.lower().endswith(".pdf")
        )
        if PDF_DIR.is_dir()
        else [],
    }

@app.post("/api/ask")
def ask(request: QueryRequest) -> Dict[str, Any]:
    """
    Primary RAG endpoint. Accepts a user query and streams it 
    through the Try/Escalate LLM architectural pipeline.
    """
    result = ask_question(request.query, request.selected_files)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

@app.get("/api/vectordb/stats")
def get_vectordb_stats() -> Dict[str, Any]:
    """
    Get statistics about the vector database for demonstration to judges.
    Shows total chunks, unique sources, and metadata distribution.
    """
    from vector_store import collection
    
    try:
        total_count = collection.count()
        
        # Get a sample of all data to analyze
        sample_size = min(total_count, 1000)
        results = collection.get(limit=sample_size, include=["metadatas"])
        
        metadatas = results.get("metadatas", [])
        
        # Analyze sources
        sources = set()
        content_types = {}
        extraction_methods = {}
        pages_count = 0
        
        for meta in metadatas:
            if meta:
                src = meta.get("source")
                if src:
                    sources.add(src)
                
                ct = meta.get("content_type")
                if ct:
                    content_types[ct] = content_types.get(ct, 0) + 1
                
                em = meta.get("extraction_method")
                if em:
                    extraction_methods[em] = extraction_methods.get(em, 0) + 1
                
                if meta.get("page") is not None:
                    pages_count += 1
        
        return {
            "total_chunks": total_count,
            "unique_documents": len(sources),
            "documents": sorted(list(sources)),
            "content_type_distribution": content_types,
            "extraction_method_distribution": extraction_methods,
            "chunks_with_page_info": pages_count,
            "sample_size_analyzed": len(metadatas),
            "collection_name": "financial_docs",
            "embedding_model": "all-MiniLM-L6-v2"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error accessing vector DB: {str(e)}")

@app.get("/api/vectordb/sample")
def get_vectordb_sample(limit: int = 10) -> Dict[str, Any]:
    """
    Get sample chunks from the vector database with full metadata.
    Perfect for showing judges the actual stored data structure.
    """
    from vector_store import collection
    
    try:
        if limit > 100:
            limit = 100
        
        results = collection.get(
            limit=limit,
            include=["documents", "metadatas", "embeddings"]
        )
        
        chunks = []
        ids = results.get("ids", [])
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])
        embeddings = results.get("embeddings", [])
        
        for i in range(len(ids)):
            chunk = {
                "chunk_id": ids[i] if i < len(ids) else None,
                "text": documents[i] if i < len(documents) else None,
                "text_length": len(documents[i]) if i < len(documents) else 0,
                "metadata": metadatas[i] if i < len(metadatas) else {},
                "embedding_dimensions": len(embeddings[i]) if i < len(embeddings) and embeddings[i] else 0,
                "embedding_sample": embeddings[i][:5] if i < len(embeddings) and embeddings[i] else []
            }
            chunks.append(chunk)
        
        return {
            "sample_count": len(chunks),
            "chunks": chunks
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching samples: {str(e)}")

@app.get("/api/vectordb/search")
def search_vectordb(query: str, limit: int = 5) -> Dict[str, Any]:
    """
    Direct vector similarity search endpoint for demonstration.
    Shows raw retrieval results with distances and metadata.
    """
    from vector_store import query_documents
    
    try:
        if limit > 50:
            limit = 50
        
        results = query_documents([query], n_results=limit, where=None)
        
        # Extract and format results
        docs = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        ids = results.get("ids", [[]])[0]
        
        search_results = []
        for i in range(len(docs)):
            result = {
                "rank": i + 1,
                "chunk_id": ids[i] if i < len(ids) else None,
                "text": docs[i] if i < len(docs) else "",
                "text_length": len(docs[i]) if i < len(docs) else 0,
                "metadata": metadatas[i] if i < len(metadatas) else {},
                "vector_distance": distances[i] if i < len(distances) else None,
                "similarity_score": round(1.0 / (1.0 + distances[i]), 4) if i < len(distances) and distances[i] is not None else 0
            }
            search_results.append(result)
        
        return {
            "query": query,
            "results_count": len(search_results),
            "results": search_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching vector DB: {str(e)}")

@app.get("/api/vectordb/document/{filename}")
def get_document_chunks(filename: str, limit: int = 50) -> Dict[str, Any]:
    """
    Get all chunks for a specific document from the vector database.
    Useful for showing judges how a single PDF is stored and chunked.
    """
    from vector_store import collection
    
    try:
        results = collection.get(
            where={"source": filename},
            limit=limit,
            include=["documents", "metadatas"]
        )
        
        chunks = []
        ids = results.get("ids", [])
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])
        
        for i in range(len(ids)):
            chunk = {
                "chunk_id": ids[i] if i < len(ids) else None,
                "text": documents[i] if i < len(documents) else None,
                "text_length": len(documents[i]) if i < len(documents) else 0,
                "metadata": metadatas[i] if i < len(metadatas) else {}
            }
            chunks.append(chunk)
        
        # Sort by page and chunk_index if available
        chunks.sort(key=lambda x: (
            x["metadata"].get("page", 0) or 0,
            x["metadata"].get("chunk_index", 0) or 0
        ))
        
        return {
            "filename": filename,
            "total_chunks": len(chunks),
            "chunks": chunks
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching document chunks: {str(e)}")

def _exit_if_port_in_use(host: str, port: int) -> None:
    """
    Uvicorn runs FastAPI lifespan (e.g. loading Chroma + embeddings) *before* it binds
    the socket. If port 8000 is taken, you otherwise waste that work then see WinError 10048.
    """
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, port))
    except OSError as e:
        print(
            "\n"
            "============================================================\n"
            f"Port {port} is already in use ({e!r}).\n\n"
            "Another process is listening (often a leftover `python3 main.py`).\n"
            "Uvicorn opens the port only *after* app startup, so the log order looks confusing.\n\n"
            "Free the port (PowerShell):\n"
            f"  Get-NetTCPConnection -LocalPort {port} -State Listen\n"
            "  Stop-Process -Id <OwningProcess> -Force\n\n"
            "Or use another port (update the frontend URL if needed):\n"
            f'  $env:PORT="8001"; python3 main.py\n'
            "============================================================\n"
        )
        raise SystemExit(1) from e
    finally:
        s.close()


if __name__ == "__main__":
    import uvicorn

    # reload=True spawns extra processes that each load sentence-transformers and can exhaust
    # Windows page file (error 1455). Enable only when explicitly requested.
    _reload = os.environ.get("UVICORN_RELOAD", "").strip().lower() in ("1", "true", "yes")
    _host = "0.0.0.0"
    port = int(os.environ.get("PORT", "8000"))
    _exit_if_port_in_use(_host, port)

    # Passing `app` avoids import-string worker quirks when reload is off.
    if _reload:
        uvicorn.run("main:app", host=_host, port=port, reload=True)
    else:
        uvicorn.run(app, host=_host, port=port, reload=False)
