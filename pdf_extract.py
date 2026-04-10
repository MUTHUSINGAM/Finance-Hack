"""
PDF text extraction and chunking only — no Chroma / torch imports.
Safe to import from multiprocessing workers on Windows without loading embeddings.

Chunks are built **per PDF page** so each vector stores an accurate ``page`` (1-based).
"""
import os
import fitz  # PyMuPDF


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


def process_single_pdf(args):
    """Worker: open PDF, extract text per page, chunk with page metadata (no vector DB)."""
    pdf_dir, file_name = args
    full_path = os.path.join(pdf_dir, file_name)
    try:
        doc = fitz.open(full_path)
        base_meta = extract_metadata(file_name)

        results = []
        global_chunk_idx = 0

        for page_index in range(len(doc)):
            page = doc[page_index]
            text = (page.get_text() or "").strip()
            if not text:
                continue

            page_chunks = chunk_text(text, chunk_size=500, overlap=50)
            page_human = page_index + 1  # 1-based page numbers for citations

            for local_idx, chunk in enumerate(page_chunks):
                meta = base_meta.copy()
                meta["chunk_index"] = global_chunk_idx
                meta["page"] = page_human
                meta["page_index"] = page_index
                results.append(
                    {
                        "id": f"{file_name}_p{page_human}_c{local_idx}_{global_chunk_idx}",
                        "document": chunk,
                        "metadata": meta,
                    }
                )
                global_chunk_idx += 1

        return results
    except Exception as e:
        print(f"Error processing {file_name}: {e}")
        return []
