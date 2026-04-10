# 🔧 Troubleshooting Guide

## Problem: content_type and extraction_method showing as NULL

### Symptoms
- Evidence section shows: `content_type: null` or `content_type: unknown`
- Evidence section shows: `extraction_method: null` or `extraction_method: unknown`
- API responses have `null` values for these fields

### Root Cause
Your vector database was created **before** the metadata tracking feature was added. The old chunks don't have these fields.

### Solution: Re-ingest PDFs

#### Option 1: Quick Fix (Recommended)
```bash
cd "e:\Hyperverge 3\CIT-Hackathon-2026"
python reingest_pdfs.py
```

Type `yes` when prompted. Wait 5-10 minutes for completion.

#### Option 2: Check First, Then Fix
```bash
cd "e:\Hyperverge 3\CIT-Hackathon-2026"
python check_and_fix_metadata.py
```

This will:
1. Check if metadata exists
2. Show sample chunks
3. Ask if you want to fix it
4. Re-ingest if you confirm

#### Option 3: Manual Re-ingestion
```bash
cd "e:\Hyperverge 3\CIT-Hackathon-2026"
python ingestion.py
```

This will detect empty database and auto-ingest, but you may need to manually clear the database first.

---

## Problem: Backend Won't Start

### Error: "Port 8000 is already in use"

**Solution:**
```powershell
# Find process using port 8000
Get-NetTCPConnection -LocalPort 8000 -State Listen

# Kill the process (replace <PID> with actual process ID)
Stop-Process -Id <PID> -Force

# Or kill all Python processes
Get-Process python | Stop-Process -Force

# Then restart
python3 main.py
```

### Error: "ModuleNotFoundError"

**Solution:**
```bash
# Install dependencies
pip install -r requirements.txt

# If specific module missing
pip install fastapi uvicorn chromadb sentence-transformers openai python-dotenv
```

### Error: "OpenAI API key not found"

**Solution:**
```bash
# Check .env file exists
ls .env

# Verify it contains:
# OPENAI_API_KEY=sk-...

# If missing, create it:
echo "OPENAI_API_KEY=your_key_here" > .env
```

---

## Problem: Frontend Won't Start

### Error: "Port 5173 is already in use"

**Solution:**
```powershell
# Find process using port 5173
Get-NetTCPConnection -LocalPort 5173 -State Listen

# Kill the process
Stop-Process -Id <PID> -Force

# Then restart
npm run dev
```

### Error: "npm: command not found"

**Solution:**
```bash
# Install Node.js from https://nodejs.org/
# Then:
cd frontend
npm install
npm run dev
```

### Error: "Cannot connect to backend"

**Solution:**
```bash
# Check backend is running
curl http://localhost:8000

# Check frontend .env
cd frontend
cat .env

# Should contain:
# VITE_API_URL=http://localhost:8000

# If missing, create it
echo "VITE_API_URL=http://localhost:8000" > .env
```

---

## Problem: Postman Not Working

### Error: "Could not get response"

**Checklist:**
1. ✅ Backend is running: `http://localhost:8000`
2. ✅ URL is correct in Postman
3. ✅ No typos in endpoint path
4. ✅ Correct HTTP method (GET vs POST)
5. ✅ Headers set correctly for POST requests

**Test:**
```bash
# Try with curl first
curl http://localhost:8000/api/vectordb/stats
```

### Error: "CORS error"

**Solution:**
CORS is already configured in `main.py`. If you still see errors:
1. Restart backend server
2. Clear browser cache
3. Check Postman settings (disable SSL verification if needed)

---

## Problem: No PDFs in Database

### Symptoms
- `/api/documents` returns empty list
- `/api/vectordb/stats` shows 0 chunks
- Queries return no results

### Solution
```bash
# Check PDFs folder
ls pdfs/

# If empty, add PDF files to pdfs/ folder

# Then re-ingest
python reingest_pdfs.py
```

---

## Problem: Slow Performance

### Symptoms
- Queries take >5 seconds
- Ingestion is very slow
- High CPU usage

### Solutions

**1. Reduce batch size during ingestion:**
Edit `ingestion.py`:
```python
ingest_pdfs(pdf_dir=str(PDF_DIR), batch_size=128)  # Reduced from 256
```

**2. Check hardware acceleration:**
```python
# In vector_store.py, check output:
# Should see: "Hardware Acceleration (CUDA) Enabled!" or "Hardware Acceleration (Mac MPS) Enabled!"
# If you see "Running on Standard CPU", that's expected on Windows without CUDA
```

**3. Limit query results:**
```python
# In router.py, reduce n_results
results = query_documents([user_query], n_results=5, where=where_clause)  # Reduced from 10
```

---

## Problem: Evidence Not Showing in Frontend

### Symptoms
- Evidence dropdown is empty
- No sources shown
- Evidence count is 0

### Solutions

**1. Check API response:**
```bash
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
```

Look for `"evidence": [...]` in response. Should not be empty.

**2. Check frontend console:**
- Open browser DevTools (F12)
- Look for JavaScript errors
- Check Network tab for API calls

**3. Verify data structure:**
```bash
# Check if chunks exist
curl http://localhost:8000/api/vectordb/stats
```

Should show `total_chunks > 0`.

---

## Problem: Metadata Still NULL After Re-ingestion

### Symptoms
- Ran `reingest_pdfs.py` successfully
- But content_type and extraction_method still show null

### Solutions

**1. Verify extraction code:**
```bash
# Check pdf_extract.py has metadata assignment
grep -n "content_type" pdf_extract.py
grep -n "extraction_method" pdf_extract.py
```

Should see lines like:
```python
meta["content_type"] = content_type
meta["extraction_method"] = extraction_method
```

**2. Check sample chunk:**
```bash
curl http://localhost:8000/api/vectordb/sample?limit=1
```

Look at the `metadata` field. Should have `content_type` and `extraction_method`.

**3. Hard reset:**
```bash
# Stop backend
# Delete database folder
rm -rf chroma_db/

# Restart backend (will auto-ingest)
python3 main.py
```

---

## Problem: PaddleOCR Not Working

### Symptoms
- All chunks show `extraction_method: native`
- No `extraction_method: paddleocr` chunks
- Scanned PDFs not being processed

### Solutions

**1. Check if PaddleOCR is installed:**
```bash
pip list | grep paddle
```

Should see `paddleocr` and `paddlepaddle`.

**2. Install PaddleOCR:**
```bash
pip install paddleocr paddlepaddle
```

**3. Check environment variable:**
```bash
# In .env or environment
USE_PADDLE_OCR=1
```

**4. Test OCR:**
```python
from ocr_paddle import paddleocr_available, use_paddle_ocr_enabled

print(f"PaddleOCR available: {paddleocr_available()}")
print(f"PaddleOCR enabled: {use_paddle_ocr_enabled()}")
```

Should both return `True`.

---

## Problem: Table Extraction Not Working

### Symptoms
- No chunks with `content_type: table`
- All chunks are `content_type: paragraph`

### Solutions

**1. Check PyMuPDF version:**
```bash
pip show PyMuPDF
```

Should be version 1.23.0 or higher for table support.

**2. Upgrade PyMuPDF:**
```bash
pip install --upgrade PyMuPDF
```

**3. Check PDF has tables:**
Not all PDFs have extractable tables. Scanned tables need OCR.

**4. Verify table extraction:**
```python
import fitz
doc = fitz.open("pdfs/your_file.pdf")
page = doc[0]
tables = page.find_tables()
print(f"Tables found: {len(tables.tables)}")
```

---

## Quick Diagnostic Script

Save as `diagnose.py`:
```python
import os
from vector_store import collection

print("=== DIAGNOSTIC REPORT ===\n")

# 1. Database stats
count = collection.count()
print(f"Total chunks: {count}")

# 2. Sample metadata
if count > 0:
    sample = collection.get(limit=5, include=["metadatas"])
    metas = sample.get("metadatas", [])
    
    has_ct = sum(1 for m in metas if m and m.get("content_type"))
    has_em = sum(1 for m in metas if m and m.get("extraction_method"))
    
    print(f"Chunks with content_type: {has_ct}/{len(metas)}")
    print(f"Chunks with extraction_method: {has_em}/{len(metas)}")
    
    if has_ct > 0:
        print("\n✅ Metadata looks good!")
    else:
        print("\n❌ Metadata missing! Run: python reingest_pdfs.py")
else:
    print("❌ Database is empty!")

# 3. PDFs
from paths import PDF_DIR
if PDF_DIR.exists():
    pdfs = [f for f in os.listdir(PDF_DIR) if f.endswith('.pdf')]
    print(f"\nPDFs found: {len(pdfs)}")
else:
    print("\n❌ PDFs folder not found!")

print("\n=== END REPORT ===")
```

Run with: `python diagnose.py`

---

## Emergency Reset

If nothing works, complete reset:

```bash
# 1. Stop all servers
# Press Ctrl+C in both terminals

# 2. Delete database
rm -rf chroma_db/

# 3. Clear Python cache
rm -rf __pycache__/
find . -type d -name "__pycache__" -exec rm -rf {} +

# 4. Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# 5. Restart backend (will auto-ingest)
python3 main.py

# 6. Restart frontend
cd frontend
npm run dev
```

---

## Getting Help

If issues persist:
1. Check error messages carefully
2. Look at terminal output
3. Check browser console (F12)
4. Verify all dependencies installed
5. Ensure PDFs are in correct folder
6. Try emergency reset above

---

## Common Mistakes

❌ **Forgetting to restart backend after code changes**
✅ Always restart: `Ctrl+C` then `python3 main.py`

❌ **Not re-ingesting after metadata changes**
✅ Run: `python reingest_pdfs.py`

❌ **Wrong port numbers**
✅ Backend: 8000, Frontend: 5173

❌ **Missing .env file**
✅ Create with: `OPENAI_API_KEY=sk-...`

❌ **PDFs in wrong folder**
✅ Should be in: `pdfs/` (not `pdf/` or `documents/`)

---

## Success Checklist

Before demo, verify:
- [ ] Backend running on port 8000
- [ ] Frontend running on port 5173
- [ ] `/api/vectordb/stats` returns data
- [ ] Sample chunks have content_type and extraction_method
- [ ] Evidence in frontend shows metadata
- [ ] Postman collection works
- [ ] No console errors
