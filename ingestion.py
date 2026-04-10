import os
import fitz  # PyMuPDF
import concurrent.futures
from vector_store import add_documents

def chunk_text(text, chunk_size=500, overlap=50):
    words = text.split()
    chunks = []
    for i in range(0, len(words), max(1, chunk_size - overlap)):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks

def extract_metadata(file_name):
    # E.g. extracted from "APPLE_2022_10K.pdf"
    clean_name = file_name.replace(".pdf", "").replace(".PDF", "")
    parts = clean_name.split("_")
    meta = {"source": file_name}
    
    if len(parts) >= 3:
        meta["ticker"] = parts[0]
        meta["year"] = parts[1]
        meta["doc_type"] = parts[2]
    return meta

def process_single_pdf(args):
    """Worker function to execute inside the parallel process pool."""
    pdf_dir, file_name = args
    full_path = os.path.join(pdf_dir, file_name)
    try:
        doc = fitz.open(full_path)
        text = "".join([page.get_text() + "\n" for page in doc])
        
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        base_meta = extract_metadata(file_name)
        
        results = []
        for idx, chunk in enumerate(chunks):
            meta = base_meta.copy()
            meta["chunk_index"] = idx
            results.append({
                "id": f"{file_name}_chunk_{idx}",
                "document": chunk,
                "metadata": meta
            })
        return results
    except Exception as e:
        print(f"Error processing {file_name}: {e}")
        return []

def ingest_pdfs(pdf_dir="./pdfs", batch_size=256):
    if not os.path.exists(pdf_dir):
        print(f"Directory {pdf_dir} does not exist. Please place PDFs in it.")
        return
        
    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf")]
    print(f"Found {len(pdf_files)} PDFs. Initiating parallel processor cluster...")

    all_chunks = []
    
    # 1. Multi-Core Parsing & Chunking (Maximum CPU utilization)
    with concurrent.futures.ProcessPoolExecutor() as executor:
        args_list = [(pdf_dir, f) for f in pdf_files]
        for results in executor.map(process_single_pdf, args_list):
            if results:
                all_chunks.extend(results)
                
    print(f"Extraction complete! Total text chunks: {len(all_chunks)}.")
    print("Initiating high-throughput hardware-accelerated batched embeddings...")

    # 2. Optimized Batch Embeddings to ChromaDB
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]
        
        ids = [item["id"] for item in batch]
        documents = [item["document"] for item in batch]
        metadatas = [item["metadata"] for item in batch]
        
        add_documents(ids, documents, metadatas)
        print(f"Embedded & stored batch {i // batch_size + 1} / {(len(all_chunks) + batch_size - 1) // batch_size} (Items: {len(batch)})")
        
    print("✅ All documents have been vectorized successfully!")

if __name__ == "__main__":
    ingest_pdfs("./pdfs")
