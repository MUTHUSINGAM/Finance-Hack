"""
Wipe the persisted Chroma store and re-ingest all PDFs (fresh metadata:
content_type, extraction_method, page, etc.).

Stop the API server first — on Windows an open Chroma handle can block deletion.

Usage:
  python reingest_pdfs.py          # prompts for confirmation
  python reingest_pdfs.py -y       # non-interactive
"""
import argparse
import os
import shutil
import subprocess
import sys

from paths import CHROMA_DIR, PDF_DIR


def _print_chroma_in_use_help() -> None:
    """WinError 32 / EBUSY: chroma.sqlite3 is open in another process (usually the API)."""
    print(
        "\n   chroma_db is locked. Another process still has Chroma open — almost always\n"
        "   the Finance-Hack server (`python main.py`) or a stuck Python job.\n"
    )
    if sys.platform == "win32":
        port = os.environ.get("PORT", "8000").strip() or "8000"
        try:
            r = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue)"
                    ".OwningProcess | Select-Object -Unique",
                ],
                capture_output=True,
                text=True,
                timeout=8,
            )
            pids = (r.stdout or "").strip()
            if pids:
                print(f"   (Detected process(es) listening on port {port}: {pids.replace(chr(10), ', ')})\n")
        except (OSError, subprocess.TimeoutExpired):
            pass
        print(
            "   On Windows, do this:\n"
            "   1) Go to the terminal where the API is running and press Ctrl+C.\n"
            "   2) Stop any other terminal that is ingesting or running this project.\n"
            "   3) If the port is still in use, find and stop that process:\n\n"
            f"      Get-NetTCPConnection -LocalPort {port} -State Listen | Select-Object OwningProcess\n"
            "      Stop-Process -Id 12345 -Force   # replace 12345 with that number\n\n"
            "   Or one line (stops every listener on that port):\n"
            f"      Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue | "
            "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }\n\n"
            "   4) Run this script again: python reingest_pdfs.py -y\n"
        )
    else:
        print(
            "   Stop `python main.py` and any other process using this project’s Chroma,\n"
            "   then run this script again.\n"
        )


def wipe_chroma_disk() -> None:
    """Remove the entire chroma_db directory so the next import gets a new DB."""
    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)


def reingest_all() -> bool:
    print("\n" + "=" * 70)
    print("WIPE VECTOR DB + RE-INGEST ALL PDFs")
    print("=" * 70)

    print(f"\nPDF folder: {PDF_DIR}")
    print(f"Chroma dir:  {CHROMA_DIR}")

    print("\nRemoving persisted vector database on disk...")
    try:
        wipe_chroma_disk()
        print("   Done — chroma_db cleared.")
    except OSError as e:
        print(f"   Failed: {e}")
        _print_chroma_in_use_help()
        return False

    # Import only after wipe so PersistentClient is not holding the old files open.
    from ingestion import ingest_pdfs

    print("\nRe-ingesting PDFs (content_type, extraction_method, page, ...)...")
    print("This may take several minutes depending on PDF count.\n")
    try:
        ingest_pdfs(pdf_dir=str(PDF_DIR), batch_size=256)
    except Exception as e:
        print(f"\nIngestion error: {e}")
        return False

    from vector_store import collection

    new_count = collection.count()
    print(f"\nNew chunks in database: {new_count}")

    sample = collection.get(limit=min(5, max(1, new_count)), include=["metadatas"])
    metas = sample.get("metadatas") or []
    ok = sum(
        1
        for m in metas
        if m and m.get("content_type") and m.get("extraction_method")
    )
    print(f"Sample chunks with content_type + extraction_method: {ok}/{len(metas)}")
    if metas[:3]:
        print("\nSample metadata:")
        for i, meta in enumerate(metas[:3], 1):
            print(
                f"   {i}. content_type={meta.get('content_type')!r}, "
                f"extraction_method={meta.get('extraction_method')!r}"
            )

    print("\nRestart the backend if it was running: python main.py")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Wipe Chroma and re-ingest all PDFs.")
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )
    args = parser.parse_args()

    if not args.yes:
        print("\nThis deletes the entire chroma_db folder and re-processes all PDFs.")
        response = input("Continue? (yes/no): ").strip().lower()
        if response not in ("yes", "y"):
            print("Cancelled.")
            return 0

    return 0 if reingest_all() else 1


if __name__ == "__main__":
    sys.exit(main())
