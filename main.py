from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from typing import Dict, Any

from router import ask_question
from budget_manager import budget_manager, BUDGET_LIMIT

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
        print("Empty vector store detected! Starting auto-ingestion...")
        print("This may take a few minutes depending on PDF count.")
        print("======================================================")
        ingest_pdfs(pdf_dir="./pdfs", batch_size=256)
        print("Ingestion complete. Server is now ready.")
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

@app.post("/api/ask")
def ask(request: QueryRequest) -> Dict[str, Any]:
    """
    Primary RAG endpoint. Accepts a user query and streams it 
    through the Try/Escalate LLM architectural pipeline.
    """
    result = ask_question(request.query)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

if __name__ == "__main__":
    import uvicorn
    # Make sure to run this via standard Uvicorn commands during development
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
