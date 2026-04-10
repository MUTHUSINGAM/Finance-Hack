# Technical Specification
## Project: CIT Hackathon 2026 - Finance Intelligence Portal

### 1. Tech Stack
- **Backend Framework:** FastAPI (Python 3.10+)
- **LLM API:** `openai` (Official Python SDK)
- **Primary LLM:** `gpt-4o-mini` (RAG Generation & Routing)
- **Fallback LLM:** `gpt-4o` (Complex Reasoning Only)
- **Embeddings Model:** `sentence-transformers/all-MiniLM-L6-v2`
- **Vector Store:** `chromadb` (Running in persistent local mode)

### 2. Environment Variables
Stored in `.env`:
```
OPENAI_API_KEY=your_key_here
```

### 3. Implementation Focus: "OpenAI Native" Router
To maximize the $8 budget, the query router relies directly on OpenAI's structured JSON outputs rather than a third-party framework:

```python
# Pseudo-implementation of OpenAI Native Router
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a routing assistant. Analyze this finance query. Output JSON with a 'complexity' key: 'basic' or 'complex'. Default to 'basic' unless heavy comparative math is required."},
        {"role": "user", "content": user_query}
    ],
    response_format={"type": "json_object"}
)
```

### 4. Token & Budget Management
- **GPT-4o-mini:** $0.150 / 1M Input Tokens, $0.600 / 1M Output Tokens.
- **GPT-4o:** $5.00 / 1M Input Tokens, $15.00 / 1M Output Tokens.
- **Budget Monitor:** The FastAPI backend will track tokens consumed per request and maintain an in-memory budget accumulator, freezing `gpt-4o` access entirely if costs exceed $6.00 to guarantee safety within the $8 limit.
