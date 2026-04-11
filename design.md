# System Design Document
## Project: CIT Hackathon 2026 - Finance Intelligence Portal

### 1. Architecture Overview
The system follows a modular, cost-optimized RAG (Retrieval-Augmented Generation) pipeline via FastAPI. To ensure we never breach the $8 budget, cloud usage is minimized to text-generation exclusively.

**Components:**
1. **Frontend:** Lightweight web interface (e.g., simple React/Vanilla JS).
2. **Backend Engine:** FastAPI handling API routing and LLM orchestration.
3. **Vector Database:** Local **ChromaDB**. No cloud DB costs.
4. **Embeddings:** Local **`sentence-transformers`** (`all-MiniLM-L6-v2`). $0 cost.
5. **LLM Generation:** OpenAI API.

### 2. OpenAI Native Query Router Logic
Instead of using heavy agentic frameworks (like LangChain), we use an **OpenAI-Native Router**:
- **Router Model:** `gpt-4o-mini` (system prompt: "Classify query complexity: 'basic' or 'complex'").
- **Cost Efficiency Focus:** `gpt-4o-mini` handles >95% of queries (basic summarization, factual RAG retrieval). High inference length per dollar.
- **Complex Escalation:** If and only if the router identifies deep multi-step financial reasoning, the system invokes `gpt-4o`.

### 3. RAG Pipeline
- **Ingestion:** Financial Docs → Local Chunking → `sentence-transformers` → ChromaDB.
- **Retrieval:** User Query → `sentence-transformers` → ChromaDB Similarity Search.
- **Generation:** Context + User Query → `gpt-4o-mini` (default).

### 4. Cost Optimization Strategy
- **$0 Embeddings:** Replaces `text-embedding-3-small`.
- **$0 Vector Storage:** Replaces Pinecone/Weaviate Cloud.
- **Micro-Routing:** 1 input token to `gpt-4o` costs ~33x more than `gpt-4o-mini`. Thus, the router strictly enforces `gpt-4o-mini` dominance.
