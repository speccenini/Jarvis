"""Hybrid document retrieval service."""

from __future__ import annotations

from pathlib import Path

from services.document_store import DocumentStore, RetrievedChunk


class RetrievalService:
    """Query the local document index and format LLM-ready context."""

    def __init__(self, store: DocumentStore, top_k: int = 6):
        self.store = store
        self.top_k = top_k

    def search(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        limit = top_k or self.top_k
        return self.store.hybrid_search(query, limit=limit)

    def build_context(self, query: str, top_k: int | None = None) -> tuple[str, list[RetrievedChunk]]:
        results = self.search(query, top_k=top_k)
        if not results:
            return "No relevant document chunks were found.", []

        blocks = []
        for index, result in enumerate(results, start=1):
            chunk = result.chunk
            source = format_source(chunk.filename, chunk.page_number, chunk.year)
            blocks.append(
                "\n".join(
                    [
                        f"[Source {index}] {source}",
                        f"score={result.score:.3f} keyword={result.keyword_score:.3f} vector={result.vector_score:.3f}",
                        chunk.text,
                    ]
                )
            )

        return "\n\n".join(blocks), results

    def stats(self) -> dict[str, object]:
        return self.store.stats()


def format_source(filename: str, page_number: int | None, year: int | None) -> str:
    parts = [Path(filename).name]
    if page_number:
        parts.append(f"page {page_number}")
    if year:
        parts.append(f"year {year}")
    return ", ".join(parts)


def format_results_for_humans(results: list[RetrievedChunk], max_chars: int = 700) -> str:
    if not results:
        return "No matching chunks found."

    lines = []
    for index, result in enumerate(results, start=1):
        chunk = result.chunk
        snippet = " ".join(chunk.text.split())[:max_chars]
        lines.append(
            "\n".join(
                [
                    f"{index}. {format_source(chunk.filename, chunk.page_number, chunk.year)}",
                    f"   score={result.score:.3f} keyword={result.keyword_score:.3f} vector={result.vector_score:.3f}",
                    f"   {snippet}",
                ]
            )
        )
    return "\n\n".join(lines)
