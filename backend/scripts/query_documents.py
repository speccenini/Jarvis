#!/usr/bin/env python3
"""Query the local Jarvis document index from the command line."""

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from services.document_service import DocumentService


def main() -> int:
    parser = argparse.ArgumentParser(description="Query Jarvis local document RAG index")
    parser.add_argument("query", nargs="+", help="Question or search query")
    parser.add_argument("--top-k", type=int, default=None, help="Number of chunks to return")
    args = parser.parse_args()

    query = " ".join(args.query)
    service = DocumentService()
    print(service.search(query, top_k=args.top_k))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
