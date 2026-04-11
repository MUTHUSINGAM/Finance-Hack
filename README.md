# Financial Intelligence Portal

A production-style Retrieval-Augmented Generation (RAG) app for analyzing financial PDFs (10-K/10-Q style documents) with scoped retrieval, evidence tracing, confidence signals, and chart-ready outputs.

## Overview

This project provides:

- PDF ingestion and chunk-level vector indexing
- Fast semantic retrieval over local ChromaDB
- Query-time scoping to selected files only
- Evidence payloads with source, page, and confidence score
- LLM answer generation with budget-aware model routing
- Graph rendering from `chart-data` JSON in chat responses

## Architecture

```mermaid
graph TD
    A[PDF files in /pdfs] --> B[pdf_extract.py]
    B --> C[Chunking + metadata source/page]
    C --> D[vector_store.py]
    D --> E[(ChromaDB at /chroma_db)]

    U[User Query + selected_files] --> R[router.py]
    R --> Q[Semantic retrieval from Chroma]
    Q --> X[Evidence build: source/page/confidence]
    X --> L[LLM answer generation]
    L --> API[/api/ask]
    API --> F[React frontend]
    F --> G[Chart rendering from chart-data]
    F --> H[Evidence drawer]
```

## End-to-End Pipeline

### 1) Ingestion and Vectorization

- PDFs are read page-by-page in `pdf_extract.py` using PyMuPDF.
- Text is split into overlapping chunks.
- Each chunk stores metadata:
  - `source` (filename)
  - `page` (1-based page number, when available)
  - `chunk_index`
- Chunks are embedded with `all-MiniLM-L6-v2` and stored in Chroma collection `financial_docs`.
- Vector store is persisted in local folder `chroma_db`.

### 2) Retrieval for a Query

- Frontend sends `/api/ask` with:
  - `query`
  - optional `selected_files`
- Router retrieves nearest chunks from Chroma:
  - If multiple files are selected, retrieval is balanced per source.
  - Scope filtering is enforced by metadata (`source`).
- Retrieved rows are converted into evidence objects:
  - `source`, `page`, `excerpt`, `vector_distance`, `retrieval_rank`, `confidence_score`.

### 3) Answer Generation

- Retrieved context is labeled as `[E1]`, `[E2]`, ...
- Prompt enforces grounded answers from retrieved context only.
- The system uses budget-aware routing:
  - primary model: `gpt-4o-mini`
  - optional escalation: `gpt-4o` when needed and budget allows

### 4) Evidence and Confidence

- Confidence is a heuristic blend of retrieval rank and vector distance similarity.
- Backend appends a `### Retrieval evidence` section from backend truth (not model guess).
- UI also shows the same evidence list in the expandable “Evidence & sources” panel.

### 5) Graph Explanation

- If the answer contains a ` ```chart-data``` ` block, frontend renders a Recharts graph.
- If model omits chart data, backend can append a fallback chart dataset so visualization still appears.

## Features

- Scoped Q&A to selected PDFs
- Balanced multi-document retrieval for comparison queries
- Page-aware citation metadata
- Confidence and evidence transparency
- Upload endpoint with safe replacement of existing vectors per file
- Budget tracking and escalation control

## API Summary

- `GET /` - health check
- `GET /api/budget` - budget usage and circuit state
- `GET /api/documents` - available PDF filenames
- `POST /api/upload` - upload and vectorize PDFs
- `POST /api/ask` - ask a question with optional scoped files

Example ask payload:

```json
{
  "query": "Compare cloud revenue trends",
  "selected_files": ["MSFT_2023_10K.pdf", "GOOGL_2023_10K.pdf"]
}
```

## Local Setup

### 1) Backend

From project root:

```bash
pip install -r requirements.txt
```

Create `.env`:

```txt
OPENAI_API_KEY=your_openai_key
```

Run API:

```bash
python3 main.py
```

Default backend URL: `http://localhost:8000` (or set `PORT=8001` etc.).

### 2) Frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend URL: `http://localhost:5173`

If backend is on a non-default port, set `frontend/.env`:

```txt
VITE_API_URL=http://localhost:8001
```

Then restart `npm run dev`.

## Data and Storage

- Input PDFs: `pdfs/`
- Vector DB: `chroma_db/`
- Metadata used for scope: `source` filename

## Notes

- If older indexed data lacks page metadata, page may show as `unknown`; re-upload/re-index PDFs to refresh metadata.
- Confidence score is a retrieval heuristic for ranking transparency, not a calibrated probability.
