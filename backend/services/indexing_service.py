"""PDF indexing pipeline for Jarvis local documents."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from services.document_store import DocumentChunk, DocumentStore


class IndexingError(Exception):
    """Raised when document indexing fails."""


@dataclass(frozen=True)
class IndexedDocument:
    file_path: str
    filename: str
    pages: int
    chunks: int
    year: int | None


class IndexingService:
    """Extract PDF text, chunk it, and write the local retrieval index."""

    def __init__(
        self,
        pdf_dir: Path,
        text_dir: Path,
        store: DocumentStore,
        chunk_size: int = 900,
        chunk_overlap: int = 150,
    ):
        self.pdf_dir = pdf_dir
        self.text_dir = text_dir
        self.store = store
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def index_all(self) -> list[IndexedDocument]:
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        pdf_files = sorted(self.pdf_dir.rglob("*.pdf"))
        return [self.index_pdf(path) for path in pdf_files]

    def index_pdf(self, pdf_path: Path) -> IndexedDocument:
        if not pdf_path.exists():
            raise IndexingError(f"PDF does not exist: {pdf_path}")
        if pdf_path.suffix.lower() != ".pdf":
            raise IndexingError(f"Not a PDF file: {pdf_path}")

        pages = extract_pdf_pages(pdf_path)
        chunks = self._build_chunks(pdf_path, pages)
        self.store.replace_file_chunks(pdf_path, chunks)
        self._write_text_copy(pdf_path, pages)

        return IndexedDocument(
            file_path=str(pdf_path.resolve()),
            filename=pdf_path.name,
            pages=len(pages),
            chunks=len(chunks),
            year=infer_year(pdf_path.name + "\n" + "\n".join(text for _, text in pages[:2])),
        )

    def _build_chunks(self, pdf_path: Path, pages: list[tuple[int, str]]) -> list[DocumentChunk]:
        year = infer_year(str(pdf_path))
        chunks = []

        for page_number, text in pages:
            if not text.strip():
                continue

            page_year = infer_year(text[:2000]) or year
            for chunk_index, chunk_text in enumerate(chunk_text_by_words(text, self.chunk_size, self.chunk_overlap)):
                chunk_id = stable_chunk_id(pdf_path, page_number, chunk_index, chunk_text)
                chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        file_path=str(pdf_path.resolve()),
                        filename=pdf_path.name,
                        page_number=page_number,
                        year=page_year,
                        text=chunk_text,
                    )
                )

        if chunks:
            embeddings = self.store.embedding_provider.embed_texts([chunk.text for chunk in chunks])
            chunks = [
                DocumentChunk(
                    chunk_id=chunk.chunk_id,
                    file_path=chunk.file_path,
                    filename=chunk.filename,
                    page_number=chunk.page_number,
                    year=chunk.year,
                    text=chunk.text,
                    embedding=embeddings[index],
                )
                for index, chunk in enumerate(chunks)
            ]

        return chunks

    def _write_text_copy(self, pdf_path: Path, pages: list[tuple[int, str]]):
        self.text_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.text_dir / f"{pdf_path.stem}.txt"
        lines = []
        for page_number, text in pages:
            lines.append(f"\n\n--- page {page_number} ---\n")
            lines.append(text)
        output_path.write_text("".join(lines).strip() + "\n", encoding="utf-8")


def extract_pdf_pages(pdf_path: Path) -> list[tuple[int, str]]:
    try:
        import fitz
    except ImportError:
        return _extract_pdf_pages_with_pypdf(pdf_path)

    pages = []
    try:
        with fitz.open(pdf_path) as document:
            for index, page in enumerate(document, start=1):
                pages.append((index, page.get_text("text") or ""))
    except Exception as exc:
        raise IndexingError(f"Could not extract PDF text from {pdf_path}: {exc}") from exc

    return pages


def _extract_pdf_pages_with_pypdf(pdf_path: Path) -> list[tuple[int, str]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise IndexingError("Install pypdf or pymupdf to index PDF documents.") from exc

    try:
        reader = PdfReader(str(pdf_path))
        return [
            (index, page.extract_text() or "")
            for index, page in enumerate(reader.pages, start=1)
        ]
    except Exception as exc:
        raise IndexingError(f"Could not extract PDF text from {pdf_path}: {exc}") from exc


def chunk_text_by_words(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    words = re.findall(r"\S+", text)
    if not words:
        return []

    overlap = max(0, min(chunk_overlap, chunk_size // 2))
    step = max(1, chunk_size - overlap)
    chunks = []

    for start in range(0, len(words), step):
        chunk_words = words[start : start + chunk_size]
        if not chunk_words:
            break
        chunks.append(" ".join(chunk_words))
        if start + chunk_size >= len(words):
            break

    return chunks


def infer_year(text: str) -> int | None:
    matches = re.findall(r"\b(20[0-4]\d|19[7-9]\d)\b", text)
    if not matches:
        return None
    return int(matches[0])


def stable_chunk_id(pdf_path: Path, page_number: int, chunk_index: int, text: str) -> str:
    digest = hashlib.sha1(
        f"{pdf_path.resolve()}:{page_number}:{chunk_index}:{text[:200]}".encode("utf-8")
    ).hexdigest()
    return digest
