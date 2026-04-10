# ⚡ Quick Start Guide

## 🎯 Goal
Get your system demo-ready with proper metadata in 15 minutes.

---

## 📋 Step-by-Step

### 1️⃣ Fix Metadata (5-10 min)

Open PowerShell in project folder:
```bash
cd "e:\Hyperverge 3\CIT-Hackathon-2026"
python reingest_pdfs.py
```

Type `yes` when asked. Wait for completion.

**✅ Success looks like:**
```
✅ SUCCESS! All chunks now have content_type and extraction_method!
```

---

### 2️⃣ Start Backend (30 sec)

```bash
python3 main.py
```

**✅ Success looks like:**
```
Vector store loaded with 61614 text chunks. Ready to serve.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Keep this terminal open!

---

### 3️⃣ Start Frontend (30 sec)

Open **NEW** terminal:
```bash
cd "e:\Hyperverge 3\CIT-Hackathon-2026\frontend"
npm run dev
```

**✅ Success looks like:**
```
VITE v8.0.8  ready in 376 ms
➜  Local:   http://localhost:5173/
```

Keep this terminal open too!

---

### 4️⃣ Import Postman Collection (1 min)

1. Open Postman
2. Click "Import"
3. Select: `Finance_Intelligence_Portal.postman_collection.json`
4. Done!

---

### 5️⃣ Test Everything (2 min)

#### Test 1: Postman
Run: `GET /api/vectordb/stats`

**Should see:**
```json
{
  "total_chunks": 61614,
  "content_type_distribution": {
    "paragraph": 45000,
    "table": 12000
  }
}
```

#### Test 2: Frontend
1. Open: http://localhost:5173
2. Ask: "What is the revenue trend?"
3. Expand "Evidence & sources"

**Should see:**
- ✅ content_type: paragraph
- ✅ extraction_method: native
- ✅ Excerpt text
- ✅ Confidence score

---

## ✅ You're Ready!

If all tests passed, you're demo-ready!

**Open these for reference:**
- `JUDGES_DEMO.md` - Demo script
- `POSTMAN_GUIDE.md` - API examples

---

## ❌ Something Broke?

### Backend won't start
```bash
Get-Process python | Stop-Process -Force
python3 main.py
```

### Frontend won't start
```bash
cd frontend
npm install
npm run dev
```

### Metadata still NULL
```bash
rm -rf chroma_db/
python3 main.py  # Will auto-ingest
```

### Still stuck?
See `TROUBLESHOOTING.md`

---

## 🎬 Demo Checklist

Before judges arrive:
- [ ] Backend running (port 8000)
- [ ] Frontend running (port 5173)
- [ ] Postman collection imported
- [ ] Test query works
- [ ] Evidence shows metadata
- [ ] Have JUDGES_DEMO.md open

**You got this!** 🚀
