# CIT-Hackathon-2026
# Finance Intelligence Portal 🚀

An ultra-efficient, budget-restricted **Retrieval-Augmented Generation (RAG)** platform designed to analyze deep financial SEC filings in real-time. Built specifically for the CIT Hackathon 2026 under a strict **$8 API constraint**.

![Bloomberg-Style UI](https://via.placeholder.com/1200x600?text=Financial+Intelligence+Terminal) *(React + Tailwind v4 + Glassmorphism)*

## 🧠 Architecture Overview

Our application consists of a decoupled high-throughput backend and a Bloomberg Terminal-inspired React frontend.

*   **Embedding Engine:** Local `sentence-transformers` (`all-MiniLM-L6-v2`) deployed directly on Apple Silicon via Metal Performance Shaders (MPS) for **$0 ingestion cost**.
*   **Vector Database:** Local **ChromaDB**. Text chunking is distributed via a Multi-core Python `ProcessPoolExecutor`.
*   **API Layer:** **FastAPI**. Auto-hydrates the vector store on initial startup using `lifespan` loaders.
*   **User Interface:** **Vite React**. Modern "Glassmorphism" patterns, responsive mathematical LaTeX parsing, and dynamic Recharts generation.
*   **Budgeting:** Hard '$7.50' token circuit breaker `budget_manager.py` integrated into the LLM Router.

---

## 💻 Setup Instructions

Be sure to follow these exact steps to launch the intelligence nodes.

### Step 1: Prepare the Data
For the internal multi-core ingestion script to work, you must actively place your raw target documents inside the `pdfs` folder.
1. Create a folder named `pdfs` in the root directory (if it doesn't exist).
2. Physically drag-and-drop all your target `.pdf` documents into this folder.

### Step 2: Configure Environment
You must provide OpenAI authentication.
1. Create a new file in the root directory named `.env`.
2. Inside `.env`, paste your API key exactly like this:
```txt
OPENAI_API_KEY=sk-proj-YOUR_EXACT_API_KEY_HERE
```

### Step 3: Run the Backend (Python)
Open a terminal in the root directory.
```bash
# Install the python vectorization and LLM dependencies
pip install -r requirements.txt

# Launch the FastAPI Server
python3 main.py
```
> [!NOTE]
> *On first boot, the backend server will automatically detect the PDFs folder and initiate parallel multiprocessing to scrape and embed the data into a local ChromaDB. This may take a few minutes.*

### Step 4: Run the Frontend (React)
Open a completely **separate** terminal window and CD into the frontend folder.
```bash
cd frontend

# Install exact UI and parsing dependencies
npm install --force

# Launch Vite hot-reload server
npm run dev
```

Browse to `http://localhost:5173` and start analyzing!
