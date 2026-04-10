# Vector Database API - Postman Guide for Judges

This guide shows how to demonstrate the vector database and RAG system using Postman.

## Base URL
```
http://localhost:8000
```

---

## 📊 Vector Database Inspection Endpoints

### 1. Get Vector Database Statistics
**Endpoint:** `GET /api/vectordb/stats`

**Description:** Shows comprehensive statistics about the vector database including total chunks, unique documents, content type distribution, and extraction method distribution.

**Postman Setup:**
- Method: `GET`
- URL: `http://localhost:8000/api/vectordb/stats`
- Headers: None required

**Response Example:**
```json
{
  "total_chunks": 61614,
  "unique_documents": 15,
  "documents": [
    "3M_2018_10K.pdf",
    "3M_2020_10K.pdf",
    "3M_2023Q2_10Q.pdf"
  ],
  "content_type_distribution": {
    "paragraph": 45000,
    "table": 12000,
    "image_ocr": 4614
  },
  "extraction_method_distribution": {
    "native": 57000,
    "paddleocr": 4614
  },
  "chunks_with_page_info": 61614,
  "sample_size_analyzed": 1000,
  "collection_name": "financial_docs",
  "embedding_model": "all-MiniLM-L6-v2"
}
```

**What to Show Judges:**
- Total number of text chunks stored
- How many unique PDF documents are indexed
- Distribution of content types (paragraphs, tables, OCR'd images)
- Extraction methods used (native PDF text vs OCR)

---

### 2. Get Sample Chunks from Vector Database
**Endpoint:** `GET /api/vectordb/sample?limit=10`

**Description:** Retrieves actual sample chunks with full metadata, text content, and embedding information.

**Postman Setup:**
- Method: `GET`
- URL: `http://localhost:8000/api/vectordb/sample?limit=10`
- Query Parameters:
  - `limit`: Number of samples (default: 10, max: 100)

**Response Example:**
```json
{
  "sample_count": 10,
  "chunks": [
    {
      "chunk_id": "3M_2023Q2_10Q.pdf_p5_c_0_123",
      "text": "Revenue for the second quarter of 2023 was $8.3 billion...",
      "text_length": 450,
      "metadata": {
        "source": "3M_2023Q2_10Q.pdf",
        "page": 5,
        "chunk_index": 123,
        "content_type": "paragraph",
        "extraction_method": "native",
        "ticker": "3M",
        "year": "2023Q2",
        "doc_type": "10Q"
      },
      "embedding_dimensions": 384,
      "embedding_sample": [0.0234, -0.1567, 0.0891, -0.0456, 0.1234]
    }
  ]
}
```

**What to Show Judges:**
- Actual text chunks stored in the database
- Rich metadata (source file, page number, content type, extraction method)
- Embedding vectors (384-dimensional from all-MiniLM-L6-v2 model)
- How the system tracks document structure

---

### 3. Vector Similarity Search
**Endpoint:** `GET /api/vectordb/search?query=revenue growth&limit=5`

**Description:** Performs direct vector similarity search showing raw retrieval results with distances.

**Postman Setup:**
- Method: `GET`
- URL: `http://localhost:8000/api/vectordb/search?query=revenue%20growth&limit=5`
- Query Parameters:
  - `query`: Search query (URL encoded)
  - `limit`: Number of results (default: 5, max: 50)

**Response Example:**
```json
{
  "query": "revenue growth",
  "results_count": 5,
  "results": [
    {
      "rank": 1,
      "chunk_id": "3M_2023Q2_10Q.pdf_p12_c_3_456",
      "text": "Revenue increased 5.2% year-over-year driven by strong demand...",
      "text_length": 380,
      "metadata": {
        "source": "3M_2023Q2_10Q.pdf",
        "page": 12,
        "content_type": "paragraph",
        "extraction_method": "native"
      },
      "vector_distance": 0.4523,
      "similarity_score": 0.6884
    }
  ]
}
```

**What to Show Judges:**
- How semantic search works (finds conceptually similar content)
- Vector distance metrics
- Ranking by relevance
- Metadata preservation through retrieval

---

### 4. Get All Chunks for a Specific Document
**Endpoint:** `GET /api/vectordb/document/{filename}?limit=50`

**Description:** Shows how a single PDF is chunked and stored in the vector database.

**Postman Setup:**
- Method: `GET`
- URL: `http://localhost:8000/api/vectordb/document/3M_2023Q2_10Q.pdf?limit=50`
- Path Parameter:
  - `filename`: PDF filename (e.g., "3M_2023Q2_10Q.pdf")
- Query Parameter:
  - `limit`: Max chunks to return (default: 50)

**Response Example:**
```json
{
  "filename": "3M_2023Q2_10Q.pdf",
  "total_chunks": 234,
  "chunks": [
    {
      "chunk_id": "3M_2023Q2_10Q.pdf_p1_c_0_0",
      "text": "UNITED STATES SECURITIES AND EXCHANGE COMMISSION...",
      "text_length": 500,
      "metadata": {
        "source": "3M_2023Q2_10Q.pdf",
        "page": 1,
        "chunk_index": 0,
        "content_type": "paragraph",
        "extraction_method": "native"
      }
    }
  ]
}
```

**What to Show Judges:**
- How a PDF is broken into chunks
- Page-by-page organization
- Different content types within one document
- Chunk overlap strategy

---

## 🤖 RAG System Endpoints

### 5. Ask a Question (RAG Pipeline)
**Endpoint:** `POST /api/ask`

**Description:** Full RAG pipeline with retrieval, evidence tracking, and LLM answer generation.

**Postman Setup:**
- Method: `POST`
- URL: `http://localhost:8000/api/ask`
- Headers:
  - `Content-Type: application/json`
- Body (raw JSON):
```json
{
  "query": "What was 3M's revenue growth in 2023?",
  "selected_files": ["3M_2023Q2_10Q.pdf"]
}
```

**Response Example:**
```json
{
  "answer": "3M's revenue showed positive growth in Q2 2023...\n\n### Retrieval evidence\n\n- **chunk_87** | **3M_2023Q2_10Q.pdf** | page 12 | **content_type:** paragraph | **extraction_method:** native | confidence **0.8032**\n  > Revenue for the second quarter of 2023 was $8.3 billion...",
  "model": "gpt-4o-mini",
  "evidence": [
    {
      "chunk_id": "3M_2023Q2_10Q.pdf_p12_c_3_87",
      "source": "3M_2023Q2_10Q.pdf",
      "page": 12,
      "excerpt": "Revenue for the second quarter of 2023 was $8.3 billion...",
      "full_text_length": 450,
      "confidence_score": 0.8032,
      "vector_distance": 0.5001,
      "retrieval_rank": 1,
      "content_type": "paragraph",
      "extraction_method": "native"
    }
  ],
  "sources_summary": "3M_2023Q2_10Q.pdf p.12; 3M_2023Q2_10Q.pdf p.15"
}
```

**What to Show Judges:**
- Complete RAG pipeline in action
- Evidence tracking with source attribution
- Content type and extraction method visibility
- Confidence scores and vector distances
- LLM-generated answer with citations

---

### 6. Get Available Documents
**Endpoint:** `GET /api/documents`

**Description:** Lists all PDF documents available in the system.

**Postman Setup:**
- Method: `GET`
- URL: `http://localhost:8000/api/documents`

**Response Example:**
```json
{
  "documents": [
    "3M_2018_10K.pdf",
    "3M_2020_10K.pdf",
    "3M_2023Q2_10Q.pdf",
    "ACTIVISIONBLIZZARD_2015_10K.pdf"
  ]
}
```

---

### 7. Get Budget Status
**Endpoint:** `GET /api/budget`

**Description:** Shows API cost tracking and circuit breaker status.

**Postman Setup:**
- Method: `GET`
- URL: `http://localhost:8000/api/budget`

**Response Example:**
```json
{
  "spent": 0.45,
  "limit": 7.5,
  "circuit_breaker_active": false
}
```

---

## 🎯 Demo Flow for Judges

### Step 1: Show Database Overview
1. Call `/api/vectordb/stats` to show total chunks and distribution
2. Highlight the content_type_distribution (tables, paragraphs, OCR)
3. Show extraction_method_distribution (native vs PaddleOCR)

### Step 2: Show Raw Data Structure
1. Call `/api/vectordb/sample?limit=5`
2. Show actual chunks with metadata
3. Point out embedding dimensions (384D vectors)
4. Explain content_type and extraction_method fields

### Step 3: Demonstrate Semantic Search
1. Call `/api/vectordb/search?query=revenue%20trends&limit=5`
2. Show how vector similarity finds relevant content
3. Highlight different content types in results (tables vs paragraphs)

### Step 4: Show Document Chunking
1. Call `/api/vectordb/document/3M_2023Q2_10Q.pdf?limit=20`
2. Show how one PDF is broken into chunks
3. Point out page numbers and content types

### Step 5: Full RAG Pipeline
1. Call `POST /api/ask` with a complex query
2. Show the evidence array with content_type and extraction_method
3. Demonstrate how tables and OCR'd content are retrieved
4. Show confidence scores and source attribution

---

## 🔍 Key Features to Highlight

### 1. Multi-Method Extraction
- **Native PDF text extraction** for digital documents
- **PaddleOCR** for scanned images and low-text pages
- **Table detection** for structured data

### 2. Rich Metadata
- `content_type`: paragraph, table, image_ocr
- `extraction_method`: native, paddleocr
- `page`: Exact page number
- `source`: Original PDF filename

### 3. Evidence Transparency
- Every answer shows which chunks were used
- Confidence scores based on retrieval rank + vector similarity
- Full source attribution with page numbers

### 4. Vector Database
- 384-dimensional embeddings (all-MiniLM-L6-v2)
- ChromaDB for fast similarity search
- Persistent storage with metadata filtering

---

## 📝 Postman Collection Import

You can import these endpoints into Postman:

1. Create a new Collection: "Finance Intelligence Portal"
2. Add requests for each endpoint above
3. Set base URL as environment variable: `{{base_url}}` = `http://localhost:8000`
4. Save example responses for quick demos

---

## 🚀 Quick Test Commands

```bash
# Get stats
curl http://localhost:8000/api/vectordb/stats

# Get samples
curl http://localhost:8000/api/vectordb/sample?limit=5

# Search
curl "http://localhost:8000/api/vectordb/search?query=revenue&limit=5"

# Ask question
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the revenue trend?"}'
```

---

## 💡 Tips for Judges Demo

1. **Start with stats** - Shows scale of the system
2. **Show sample chunks** - Proves data is actually stored with metadata
3. **Demonstrate search** - Shows vector similarity in action
4. **Run RAG query** - Complete end-to-end pipeline
5. **Point out content_type/extraction_method** - Unique feature showing multi-modal extraction
6. **Highlight tables and OCR** - Show how system handles complex documents
