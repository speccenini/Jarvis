"""High-level document QA service for Jarvis."""

from __future__ import annotations

from dataclasses import dataclass

from config import Config
from codex_bridge import run_codex
from services.document_store import DocumentStore
from services.embedding_service import build_embedding_provider
from services.indexing_service import IndexedDocument, IndexingService
from services.retrieval_service import RetrievalService, format_results_for_humans


class DocumentServiceError(Exception):
    """Raised when document QA cannot run."""


@dataclass(frozen=True)
class DocumentSearchResult:
    answer: str
    source_count: int


class DocumentService:
    """Facade for indexing, retrieval, and document-grounded answers."""

    def __init__(self):
        embedding_provider = build_embedding_provider(
            Config.EMBEDDING_PROVIDER,
            openai_api_key=Config.OPENAI_API_KEY,
            openai_model=Config.OPENAI_EMBEDDING_MODEL,
        )
        self.store = DocumentStore(
            db_path=Config.DOCUMENTS_METADATA_DB,
            chroma_dir=Config.DOCUMENTS_CHROMA_DIR,
            embedding_provider=embedding_provider,
            use_chroma=Config.DOCUMENTS_USE_CHROMA,
        )
        self.indexing = IndexingService(
            pdf_dir=Config.DOCUMENTS_PDF_DIR,
            text_dir=Config.DOCUMENTS_TEXT_DIR,
            store=self.store,
            chunk_size=Config.DOCUMENTS_CHUNK_SIZE,
            chunk_overlap=Config.DOCUMENTS_CHUNK_OVERLAP,
        )
        self.retrieval = RetrievalService(self.store, top_k=Config.DOCUMENTS_TOP_K)

    def index_all(self) -> list[IndexedDocument]:
        return self.indexing.index_all()

    def search(self, query: str, top_k: int | None = None) -> str:
        results = self.retrieval.search(query, top_k=top_k)
        return format_results_for_humans(results)

    async def answer(self, question: str, top_k: int | None = None) -> DocumentSearchResult:
        context, results = self.retrieval.build_context(question, top_k=top_k)
        if not results:
            return DocumentSearchResult(
                answer=(
                    "Non ho trovato chunk rilevanti nell'indice documenti. "
                    "Indicizza i PDF con /docs index oppure ./backend/scripts/index_documents.py."
                ),
                source_count=0,
            )

        prompt = f"""
Answer the user's question using only the document context below.

Rules:
- Answer in Italian unless the user asks otherwise.
- If the context is insufficient, say what is missing.
- Include concise source references with filename and page number when available.
- Do not invent facts outside the provided context.

Document context:
{context}

Question:
{question}
"""
        answer = await run_codex(prompt)
        return DocumentSearchResult(answer=answer, source_count=len(results))

    def stats(self) -> dict[str, object]:
        return self.retrieval.stats()
