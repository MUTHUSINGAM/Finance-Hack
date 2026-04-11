# PLAN-backend-infrastructure

## Goal
Initialize the backend foundation for the Finance Intelligence Portal, including FastAPI, ChromaDB local vector store, PyMuPDF chunking pipeline, and the $8 budget "Try / Escalate" OpenAI router logic.

## Tasks
- [x] Task 1: Initialize project structure and `requirements.txt`.
- [x] Task 2: Implement `budget_manager.py` with hard circuit breaker at $7.50.
- [x] Task 3: Implement `vector_store.py` using local `sentence-transformers` and `ChromaDB`.
- [x] Task 4: Implement `ingestion.py` using `PyMuPDF` with batch size of 5 and 500-token chunks.
- [x] Task 5: Implement `router.py` with "Try / Escalate" logic to optimize GPT-4o-mini vs GPT-4o.
- [x] Task 6: Implement `main.py` adding FastAPI endpoints.

## Done When
- [ ] Backend is running.
- [ ] Endpoints `/ask` and `/budget` are functional.
- [ ] Ingestion script processes PDFs in batches.
- [ ] `budget_state.json` accurately tracks LLM spend limit.
