"""Resolve data dirs from the project root (not the process cwd)."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
PDF_DIR = PROJECT_ROOT / "pdfs"
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
