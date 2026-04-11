# 🔥 URGENT: Fix NULL Metadata Issue

## The Problem

Your evidence is showing:
- `content_type: null` ❌
- `extraction_method: null` ❌

This happens because your vector database was created **before** the metadata tracking feature was added.

---

## The Solution (5 Minutes)

### Step 1: Run the Fix Script

```bash
cd "e:\Hyperverge 3\CIT-Hackathon-2026"
python reingest_pdfs.py
```

### Step 2: Confirm When Prompted

```
⚠️  WARNING: This will delete all existing chunks and re-process all PDFs.
   This is necessary to add content_type and extraction_method metadata.

❓ Continue? (yes/no): yes    ← Type "yes" and press Enter
```

### Step 3: Wait for Completion (5-10 minutes)

You'll see:
```
🗑️  Clearing existing database...
   Deleted 61614/61614 chunks...
   ✅ Database cleared!

📥 Re-ingesting PDFs with content_type and extraction_method...
   This may take several minutes depending on PDF count...

Found 15 PDFs. Parsing PDFs in parallel...
Extraction complete! Total text chunks: 61614.
Initiating batched embeddings...
Embedded & stored batch 1 / 241 (Items: 256)
...
✅ All documents have been vectorized successfully!

✅ Re-ingestion complete!
📊 New chunks in database: 61614

🔍 Verifying metadata...
   Chunks with metadata: 5/5

✅ SUCCESS! All chunks now have content_type and extraction_method!
```

### Step 4: Restart Backend

```bash
# Stop current backend (Ctrl+C in the terminal)
python3 main.py
```

### Step 5: Test It

**Option A: Test in Postman**
```
GET http://localhost:8000/api/vectordb/sample?limit=3
```

Look for:
```json
{
  "metadata": {
    "content_type": "paragraph",        ← Should NOT be null
    "extraction_method": "native"       ← Should NOT be null
  }
}
```

**Option B: Test in Frontend**
1. Open: http://localhost:5173
2. Ask: "What is the revenue trend?"
3. Expand "Evidence & sources"
4. Should see:
   - ✅ `content_type: paragraph` (or table/image_ocr)
   - ✅ `extraction_method: native` (or paddleocr)

---

## What This Does

### Before Fix:
```
Chunk in database:
{
  "text": "Revenue was $8.3 billion...",
  "metadata": {
    "source": "3M_2023Q2_10Q.pdf",
    "page": 12,
    "content_type": null,           ← Missing!
    "extraction_method": null       ← Missing!
  }
}
```

### After Fix:
```
Chunk in database:
{
  "text": "Revenue was $8.3 billion...",
  "metadata": {
    "source": "3M_2023Q2_10Q.pdf",
    "page": 12,
    "content_type": "paragraph",        ← Fixed!
    "extraction_method": "native"       ← Fixed!
  }
}
```

---

## Why This Happens

The metadata tracking feature (`content_type` and `extraction_method`) was added to the code, but your existing vector database was created **before** this feature existed.

The old chunks don't have these fields, so they show as `null`.

**The only way to fix this is to re-process all PDFs** so the new extraction code can add the metadata.

---

## What Gets Added

### content_type
- `"paragraph"` - Regular text content
- `"table"` - Structured tabular data
- `"image_ocr"` - OCR'd scanned images

### extraction_method
- `"native"` - PyMuPDF text extraction
- `"paddleocr"` - OCR for scanned pages

---

## Time Required

- **Small database** (1-5 PDFs): 2-3 minutes
- **Medium database** (10-20 PDFs): 5-7 minutes
- **Large database** (50+ PDFs): 10-15 minutes

The process is **fully automated** - just run the script and wait.

---

## Safety Notes

✅ **Safe:**
- Your original PDF files are NOT modified
- They remain in the `pdfs/` folder
- Only the vector database is rebuilt

⚠️ **Important:**
- This will delete existing vector embeddings
- They will be recreated from the PDFs
- Any custom annotations in the database will be lost (but you don't have any)

---

## Alternative: Check First

If you want to **check before fixing**:

```bash
python check_and_fix_metadata.py
```

This will:
1. Show current metadata status
2. Display sample chunks
3. Ask if you want to fix it
4. Only proceed if you confirm

---

## Verification

After running the fix, verify it worked:

### Check 1: Database Stats
```bash
curl http://localhost:8000/api/vectordb/stats
```

Should show:
```json
{
  "content_type_distribution": {
    "paragraph": 45000,
    "table": 12000,
    "image_ocr": 4614
  },
  "extraction_method_distribution": {
    "native": 57000,
    "paddleocr": 4614
  }
}
```

### Check 2: Sample Chunks
```bash
curl http://localhost:8000/api/vectordb/sample?limit=1
```

Should have:
```json
{
  "metadata": {
    "content_type": "paragraph",        ← NOT null
    "extraction_method": "native"       ← NOT null
  }
}
```

### Check 3: Evidence in Frontend
Ask a question and check evidence section shows:
- ✅ content_type: paragraph (or table/image_ocr)
- ✅ extraction_method: native (or paddleocr)
- ✅ Excerpt text
- ✅ Confidence score

---

## If It Still Shows NULL

If metadata is still null after re-ingestion:

1. **Verify extraction code has metadata:**
   ```bash
   grep -n "content_type" pdf_extract.py
   ```
   Should see: `meta["content_type"] = content_type`

2. **Check sample directly:**
   ```bash
   curl http://localhost:8000/api/vectordb/sample?limit=1
   ```

3. **Try hard reset:**
   ```bash
   # Stop backend
   rm -rf chroma_db/
   python3 main.py  # Will auto-ingest
   ```

4. **Check TROUBLESHOOTING.md** for more solutions

---

## Quick Commands

```bash
# Fix the metadata
python reingest_pdfs.py

# Check status first
python check_and_fix_metadata.py

# Restart backend
python3 main.py

# Test in Postman
curl http://localhost:8000/api/vectordb/sample?limit=3

# Test in browser
# Open: http://localhost:5173
```

---

## Expected Timeline

```
00:00 - Run reingest_pdfs.py
00:01 - Confirm with "yes"
00:02 - Clearing database (fast)
00:03 - Extracting PDFs (parallel processing)
00:05 - Creating embeddings (batch 1/241)
00:08 - Creating embeddings (batch 120/241)
00:10 - Creating embeddings (batch 241/241)
00:11 - Verification
00:12 - ✅ Complete!
```

---

## Bottom Line

**Run this command:**
```bash
python reingest_pdfs.py
```

**Type:** `yes`

**Wait:** 5-10 minutes

**Result:** ✅ Metadata fixed!

---

## Need Help?

See **TROUBLESHOOTING.md** for detailed solutions to common issues.
