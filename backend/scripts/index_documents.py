#!/usr/bin/env python3
"""Index local PDF documents for Jarvis RAG."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from config import Config
from services.document_service import DocumentService


def main() -> int:
    service = DocumentService()
    indexed = service.index_all()
    stats = service.stats()

    print(f"PDF directory: {Config.DOCUMENTS_PDF_DIR}")
    if not indexed:
        print("No PDF files found.")
    for item in indexed:
        year = item.year if item.year else "unknown"
        print(f"- {item.filename}: {item.pages} pages, {item.chunks} chunks, year={year}")

    print(
        "Index stats: "
        f"{stats['files']} files, {stats['chunks']} chunks, "
        f"embedding={stats['embedding_provider']}, chroma={stats['chroma_enabled']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
