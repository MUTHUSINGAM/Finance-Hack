import os
import concurrent.futures

from paths import PDF_DIR
from pdf_extract import process_single_pdf


def ingest_pdfs(pdf_dir=None, batch_size=256):
    if pdf_dir is None:
        pdf_dir = str(PDF_DIR)
    from vector_store import add_documents

    if not os.path.exists(pdf_dir):
        print(f"Directory {pdf_dir} does not exist. Please place PDFs in it.")
        return

    pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf")]
    print(f"Found {len(pdf_files)} PDFs. Parsing PDFs in parallel (workers do not load ML models)...")

    all_chunks = []

    # ProcessPool workers only import pdf_extract (PyMuPDF), not torch/Chroma
    env_workers = os.environ.get("INGEST_MAX_WORKERS", "").strip()
    cap = int(env_workers) if env_workers.isdigit() and int(env_workers) > 0 else 4
    max_workers = min(cap, len(pdf_files), (os.cpu_count() or 2))
    if max_workers < 1:
        max_workers = 1
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        args_list = [(pdf_dir, f) for f in pdf_files]
        for results in executor.map(process_single_pdf, args_list):
            if results:
                all_chunks.extend(results)

    print(f"Extraction complete! Total text chunks: {len(all_chunks)}.")
    print("Initiating batched embeddings...")

    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]

        ids = [item["id"] for item in batch]
        documents = [item["document"] for item in batch]
        metadatas = [item["metadata"] for item in batch]

        add_documents(ids, documents, metadatas)
        print(
            f"Embedded & stored batch {i // batch_size + 1} / "
            f"{(len(all_chunks) + batch_size - 1) // batch_size} (Items: {len(batch)})"
        )

    print("✅ All documents have been vectorized successfully!")


if __name__ == "__main__":
    ingest_pdfs()
