# Product Requirements Document (PRD)
## Project Name: CIT Hackathon 2026 - Finance Intelligence Portal

### 1. Overview
The Finance Intelligence Portal is a modern Retrieval-Augmented Generation (RAG) platform designed to process, retrieve, and synthesize financial data efficiently. Built for the CIT Hackathon 2026, it prioritizes high-accuracy intelligence retrieval within a strict $8 operating budget constraint.

### 2. Goals & Objectives
- **Accurate Intelligence:** Synthesize complex financial queries and provide verifiable answers.
- **Extreme Budget Optimization:** Remain strictly under an $8 API budget. 
- **Low Latency:** Ensure responsive insights using localized vector stores and embedding models.

### 3. Core Features
- **Intelligent Query Routing:** Determines query complexity and routes securely to either the cost-efficient model or the advanced reasoning model.
- **Document Ingestion & Retrieval:** Parses financial PDFs/reports, generates local embeddings, and searches via local ChromaDB.
- **Chat Interface:** Easy-to-use search and chat interface for financial queries.

### 4. Constraints & Budgeting
- **Total OpenAI Budget:** $8.
- **Cost Reduction Strategy:** Zero API cost for embeddings (using local `sentence-transformers`). Strict limits on the usage of GPT-4o.
- **Time/Scope:** Hackathon constraints apply; deliver a fast, functional MVP.
