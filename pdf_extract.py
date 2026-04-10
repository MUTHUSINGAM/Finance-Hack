"""
PDF text extraction and chunking only — no Chroma / torch imports.
Safe to import from multiprocessing workers on Windows without loading embeddings.

Chunks are built **per PDF page** so each vector stores an accurate ``page`` (1-based).

Metadata per chunk (stored in Chroma):
- ``extraction_method``: ``native`` | ``paddleocr``
- ``content_type``: ``paragraph`` | ``table`` | ``image_ocr``
- ``page``: 1-based page number
Optional: ``table_id`` (int) for native table chunks from PyMuPDF.
"""
import os
import fitz  # PyMuPDF

from ocr_paddle import ocr_page_fitz, paddleocr_available, use_paddle_ocr_enabled

# Fewer than this many characters of native text → try PaddleOCR on rendered page (if installed).
MIN_NATIVE_TEXT_CHARS = int(os.getenv("MIN_NATIVE_TEXT_CHARS", "50"))


def chunk_text(text, chunk_size=500, overlap=50):
    words = text.split()
    chunks = []
    for i in range(0, len(words), max(1, chunk_size - overlap)):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks


def extract_metadata(file_name):
    clean_name = file_name.replace(".pdf", "").replace(".PDF", "")
    parts = clean_name.split("_")
    meta = {"source": file_name}

    if len(parts) >= 3:
        meta["ticker"] = parts[0]
        meta["year"] = parts[1]
        meta["doc_type"] = parts[2]
    return meta


def _extract_tables_native(page):
    """Return list of (table_text, table_index) from PyMuPDF, if available."""
    out = []
    try:
        tf = page.find_tables()
    except Exception:
        return out
    tables = getattr(tf, "tables", None)
    if tables is None:
        try:
            tables = list(tf)
        except Exception:
            return out
    for ti, tab in enumerate(tables):
        try:
            rows = tab.extract()
        except Exception:
            continue
        if not rows:
            continue
        lines = []
        for row in rows:
            if row is None:
                continue
            cells = [str(c or "").strip() for c in row]
            lines.append("\t".join(cells))
        text = "\n".join(lines).strip()
        if text:
            out.append((text, ti))
    return out


def _append_chunks(
    results,
    file_name,
    base_meta,
    page_human,
    page_index,
    text,
    extraction_method,
    content_type,
    global_chunk_idx,
    table_id=None,
    id_prefix="c",
):
    """Split text into word chunks and append result dicts."""
    page_chunks = chunk_text(text, chunk_size=500, overlap=50)
    if not page_chunks and text.strip():
        page_chunks = [text.strip()]
    for local_idx, chunk in enumerate(page_chunks):
        meta = base_meta.copy()
        meta["chunk_index"] = global_chunk_idx
        meta["page"] = page_human
        meta["page_index"] = page_index
        meta["extraction_method"] = extraction_method
        meta["content_type"] = content_type
        if table_id is not None:
            meta["table_id"] = int(table_id)
        tid = f"t{table_id}" if table_id is not None else id_prefix
        results.append(
            {
                "id": f"{file_name}_p{page_human}_{tid}_{local_idx}_{global_chunk_idx}",
                "document": chunk,
                "metadata": meta,
            }
        )
        global_chunk_idx += 1
    return global_chunk_idx


def process_single_pdf(args):
    """Worker: open PDF, extract text per page, chunk with page metadata (no vector DB)."""
    pdf_dir, file_name = args
    full_path = os.path.join(pdf_dir, file_name)
    ocr_ok = paddleocr_available() and use_paddle_ocr_enabled()

    try:
        doc = fitz.open(full_path)
        base_meta = extract_metadata(file_name)

        results = []
        global_chunk_idx = 0

        for page_index in range(len(doc)):
            page = doc[page_index]
            page_human = page_index + 1

            # 1) Native vector tables (structured cells → searchable text)
            for tbl_text, tbl_idx in _extract_tables_native(page):
                global_chunk_idx = _append_chunks(
                    results,
                    file_name,
                    base_meta,
                    page_human,
                    page_index,
                    tbl_text,
                    "native",
                    "table",
                    global_chunk_idx,
                    table_id=tbl_idx,
                )

            text = (page.get_text() or "").strip()

            # 2) Native body text
            if len(text) >= MIN_NATIVE_TEXT_CHARS:
                global_chunk_idx = _append_chunks(
                    results,
                    file_name,
                    base_meta,
                    page_human,
                    page_index,
                    text,
                    "native",
                    "paragraph",
                    global_chunk_idx,
                )
            elif ocr_ok:
                # 3) Scanned / low-text pages → PaddleOCR on rasterized page
                ocr_text, ocr_ct = ocr_page_fitz(page)
                ocr_text = (ocr_text or "").strip()
                if ocr_text:
                    global_chunk_idx = _append_chunks(
                        results,
                        file_name,
                        base_meta,
                        page_human,
                        page_index,
                        ocr_text,
                        "paddleocr",
                        ocr_ct,
                        global_chunk_idx,
                        id_prefix="ocr",
                    )

        return results
    except Exception as e:
        print(f"Error processing {file_name}: {e}")
        return []
