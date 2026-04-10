# 🚀 Quick Demo Setup Guide

## Before the Judges Arrive

### 1. Start Backend Server
```bash
cd "e:\Hyperverge 3\CIT-Hackathon-2026"
python3 main.py
```

**Expected output:**
```
Vector store loaded with 61614 text chunks. Ready to serve.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 2. Start Frontend
```bash
cd "e:\Hyperverge 3\CIT-Hackathon-2026\frontend"
npm run dev
```

**Expected output:**
```
VITE v8.0.8  ready in 376 ms
➜  Local:   http://localhost:5173/
```

### 3. Import Postman Collection
1. Open Postman
2. Click "Import"
3. Select file: `Finance_Intelligence_Portal.postman_collection.json`
4. Collection will appear with all endpoints ready

### 4. Test Everything Works

**Quick test in browser:**
- Open: `http://localhost:8000/api/vectordb/stats`
- Should see JSON with database statistics

**Quick test in Postman:**
- Run "Get Vector DB Statistics"
- Should return data about chunks and documents

**Quick test in frontend:**
- Open: `http://localhost:5173`
- Ask: "What is the revenue trend?"
- Expand "Evidence & sources"
- Verify you see content_type and extraction_method

---

## 📋 Demo Checklist

Before starting:
- [ ] Backend running (port 8000)
- [ ] Frontend running (port 5173)
- [ ] Postman collection imported
- [ ] Test query works in frontend
- [ ] Test API works in Postman
- [ ] Have JUDGES_DEMO.md open for reference
- [ ] Browser tabs ready:
  - Frontend: http://localhost:5173
  - Postman open
- [ ] Know your talking points

---

## 🎯 5-Minute Demo Flow

### Minute 1: Introduction
**Say:** "We built a financial document intelligence system with transparent evidence tracking."

**Show:** Frontend - ask a question, expand evidence
**Point out:** content_type, extraction_method, excerpt

### Minute 2: Vector Database Stats
**Open:** Postman → "Get Vector DB Statistics"
**Say:** "Our system has processed X documents into Y chunks with Z different content types."

**Highlight:**
- Total chunks
- Content type distribution
- Extraction method distribution

### Minute 3: Show Raw Data
**Open:** Postman → "Get Sample Chunks"
**Say:** "Here's the actual data structure with 384-dimensional embeddings."

**Highlight:**
- metadata.content_type
- metadata.extraction_method
- embedding_dimensions: 384

### Minute 4: Semantic Search
**Open:** Postman → "Vector Similarity Search"
**Say:** "This is pure semantic search - finds related content without exact keywords."

**Highlight:**
- Vector distances
- Mixed content types in results
- Metadata preservation

### Minute 5: Full RAG Pipeline
**Open:** Postman → "Ask Question (RAG Pipeline)"
**Say:** "Complete pipeline: retrieval → evidence tracking → answer generation with full transparency."

**Highlight:**
- Evidence array with metadata
- content_type and extraction_method visible
- Confidence scores
- Page citations

---

## 💡 Key Points to Emphasize

### 1. Multi-Modal Extraction
> "We don't just extract text - we understand structure. Paragraphs, tables, and OCR'd images are all tracked separately."

### 2. Evidence Transparency
> "Every answer shows exactly where it came from - including the content type and extraction method. Users can trust the source."

### 3. Production Ready
> "This isn't a prototype - it's a complete system with budget tracking, error handling, and scalable architecture."

---

## 🎤 Opening Statement (30 seconds)

> "We built a financial document intelligence system that solves a critical problem: trust. When AI answers questions about financial data, users need to know the source. Our system tracks not just where information comes from, but what type of content it is - whether it's a paragraph, a table, or an OCR'd scanned image - and how it was extracted. This metadata flows through our entire RAG pipeline, giving complete transparency from extraction to answer generation."

---

## 🎬 Closing Statement (30 seconds)

> "What makes this unique is the metadata tracking. Every chunk in our vector database knows its content type and extraction method. This isn't just about getting answers - it's about trusting them. With 61,000+ chunks indexed and complete evidence transparency, our system provides the reliability that financial analysis demands."

---

## ❓ Quick Q&A Prep

**Q: How does it handle scanned documents?**
**A:** "PaddleOCR automatically processes pages with minimal native text. We tag these chunks with extraction_method: 'paddleocr' for transparency."

**Q: What about tables?**
**A:** "PyMuPDF's native table detection extracts structured data. Each table chunk is tagged with content_type: 'table' and maintains its structure."

**Q: How accurate are the citations?**
**A:** "100% accurate page-level citations. Every chunk stores its exact page number during extraction and preserves it through retrieval."

**Q: What's your tech stack?**
**A:** "Python backend with FastAPI, ChromaDB vector database, all-MiniLM-L6-v2 embeddings, OpenAI for generation, React frontend."

**Q: How do you handle cost?**
**A:** "Budget-aware routing: GPT-4o-mini for most queries, automatic escalation to GPT-4o for complex questions, with circuit breaker at $7.50 limit."

---

## 🔧 Troubleshooting

### Backend won't start
```bash
# Check if port is in use
Get-NetTCPConnection -LocalPort 8000 -State Listen

# Kill the process
Stop-Process -Id <PID> -Force

# Restart
python3 main.py
```

### Frontend won't start
```bash
# Check if port is in use
Get-NetTCPConnection -LocalPort 5173 -State Listen

# Kill and restart
npm run dev
```

### Postman not connecting
- Verify backend is running: http://localhost:8000
- Check CORS is enabled (already configured)
- Try health check: GET http://localhost:8000/

### Evidence not showing metadata
- Restart backend server (new code needs to load)
- Clear browser cache
- Verify API response includes content_type and extraction_method

---

## 📱 URLs to Have Ready

- **Frontend:** http://localhost:5173
- **Backend:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/
- **Vector DB Stats:** http://localhost:8000/api/vectordb/stats

---

## 📚 Reference Documents

Keep these open during demo:
1. **JUDGES_DEMO.md** - Detailed demo script
2. **POSTMAN_GUIDE.md** - Complete API documentation
3. **This file** - Quick reference

---

## ✅ Final Checklist

5 minutes before demo:
- [ ] Backend running and responsive
- [ ] Frontend loaded and tested
- [ ] Postman collection ready
- [ ] Test query successful
- [ ] Know your opening statement
- [ ] Know your closing statement
- [ ] Confident about Q&A
- [ ] Excited to show your work! 🎉

---

## 🎯 Success Criteria

After demo, judges should know:
1. ✅ System extracts multiple content types (text, tables, OCR)
2. ✅ Every chunk has content_type and extraction_method metadata
3. ✅ Complete evidence transparency in answers
4. ✅ Vector database is inspectable and well-structured
5. ✅ Production-ready with proper error handling and cost controls

---

## 🚀 You Got This!

Remember:
- Speak clearly and confidently
- Show, don't just tell
- Highlight the unique features
- Be ready for questions
- Smile and be enthusiastic!

**Good luck with your demo!** 🎉
