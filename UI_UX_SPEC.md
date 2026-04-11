# UI/UX Specification
## Project: CIT Hackathon 2026 - Finance Intelligence Portal

### 1. Visual Aesthetics
- **Theme:** Professional, highly specialized financial tool (Dark mode default).
- **Color Palette:** 
  - Deep Slate Backgrounds
  - Accent: Emerald Green (to represent finance/success)
  - Text: High-contrast off-white/gray.

### 2. Core Interface Elements
- **Main Chat / Search Console:** A central input area similar to modern LLM portals (ChatGPT/Claude).
- **Complexity Indicator:** When a query is routed, visibly show the user which engine is working:
  - *"⚡ Processing via Fast Engine (GPT-4o-mini)"*
  - *"🧠 Deep Reasoning Initiated (GPT-4o)"*
- **Source Citations:** Financial answers must include expandable inline citations pointing to the RAG database source document to build trust.

### 3. Budget & Observability Widget
- **Current Spend Tracker:** A small, sleek widget in the bottom-left corner displaying the hackathon budget (e.g., "$1.20 / $8.00 Used").
- **Local Indicator:** A continuous green dot indicating "Local Vector Core Active" to emphasize the cost-saving architecture to the hackathon judges.

### 4. User Flow
1. User uploads a financial PDF (Processed locally via Chroma) -> Feedback: "Local Embeddings Generated ($0 cost)."
2. User submits query.
3. UI shows routing decision (Mini vs. O).
4. Results displayed with highlighted RAG citations.
