"""SQLite and optional Chroma storage for document chunks."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from services.embedding_service import EmbeddingProvider, cosine_similarity


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    file_path: str
    filename: str
    page_number: int | None
    year: int | None
    text: str
    embedding: list[float] | None = None


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: DocumentChunk
    score: float
    keyword_score: float
    vector_score: float


class DocumentStore:
    """Chunk metadata, FTS search, and optional Chroma vector index."""

    def __init__(
        self,
        db_path: Path,
        chroma_dir: Path,
        embedding_provider: EmbeddingProvider,
        use_chroma: bool = True,
    ):
        self.db_path = db_path
        self.chroma_dir = chroma_dir
        self.embedding_provider = embedding_provider
        self.use_chroma = use_chroma
        self.collection = self._build_chroma_collection() if use_chroma else None
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self):
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    page_number INTEGER,
                    year INTEGER,
                    text TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    indexed_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
                USING fts5(chunk_id UNINDEXED, filename, year UNINDEXED, text)
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_chunks_file_path ON chunks(file_path)")

    def _build_chroma_collection(self):
        try:
            import chromadb
        except ImportError:
            return None

        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self.chroma_dir))
        return client.get_or_create_collection(
            name="jarvis_documents",
            metadata={"description": "Jarvis local PDF chunks"},
        )

    def replace_file_chunks(self, file_path: Path, chunks: list[DocumentChunk]):
        resolved = str(file_path.resolve())
        now = datetime.now().astimezone().isoformat(timespec="seconds")

        with self._connect() as connection:
            existing = connection.execute(
                "SELECT chunk_id FROM chunks WHERE file_path = ?",
                (resolved,),
            ).fetchall()
            existing_ids = [row["chunk_id"] for row in existing]

            connection.execute("DELETE FROM chunks WHERE file_path = ?", (resolved,))
            for chunk_id in existing_ids:
                connection.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (chunk_id,))

            for chunk in chunks:
                embedding = chunk.embedding or []
                connection.execute(
                    """
                    INSERT INTO chunks (
                        chunk_id, file_path, filename, page_number, year, text,
                        embedding_json, indexed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.chunk_id,
                        chunk.file_path,
                        chunk.filename,
                        chunk.page_number,
                        chunk.year,
                        chunk.text,
                        json.dumps(embedding),
                        now,
                    ),
                )
                connection.execute(
                    "INSERT INTO chunks_fts (chunk_id, filename, year, text) VALUES (?, ?, ?, ?)",
                    (chunk.chunk_id, chunk.filename, str(chunk.year or ""), chunk.text),
                )

        if self.collection:
            if existing_ids:
                try:
                    self.collection.delete(ids=existing_ids)
                except Exception:
                    pass

            if not chunks:
                return

            self.collection.upsert(
                ids=[chunk.chunk_id for chunk in chunks],
                embeddings=[chunk.embedding or [] for chunk in chunks],
                documents=[chunk.text for chunk in chunks],
                metadatas=[
                    {
                        "file_path": chunk.file_path,
                        "filename": chunk.filename,
                        "page_number": chunk.page_number or 0,
                        "year": chunk.year or 0,
                    }
                    for chunk in chunks
                ],
            )

    def keyword_search(self, query: str, limit: int = 10) -> list[RetrievedChunk]:
        fts_query = self._to_fts_query(query)
        if not fts_query:
            return []

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT c.*, bm25(chunks_fts) AS rank
                FROM chunks_fts
                JOIN chunks c ON c.chunk_id = chunks_fts.chunk_id
                WHERE chunks_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (fts_query, limit),
            ).fetchall()

        results = []
        for row in rows:
            rank = float(row["rank"])
            keyword_score = 1.0 / (1.0 + max(rank, 0.0))
            results.append(
                RetrievedChunk(
                    chunk=self._row_to_chunk(row),
                    score=keyword_score,
                    keyword_score=keyword_score,
                    vector_score=0.0,
                )
            )
        return results

    def vector_search(self, query: str, limit: int = 10) -> list[RetrievedChunk]:
        query_embedding = self.embedding_provider.embed_query(query)

        if self.collection:
            try:
                response = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=limit,
                    include=["distances"],
                )
                ids = response.get("ids", [[]])[0]
                distances = response.get("distances", [[]])[0]
                return self._chunks_by_chroma_ids(ids, distances)
            except Exception:
                pass

        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM chunks").fetchall()

        scored = []
        for row in rows:
            chunk = self._row_to_chunk(row)
            similarity = cosine_similarity(query_embedding, chunk.embedding or [])
            vector_score = (similarity + 1.0) / 2.0
            scored.append(
                RetrievedChunk(
                    chunk=chunk,
                    score=vector_score,
                    keyword_score=0.0,
                    vector_score=vector_score,
                )
            )

        return sorted(scored, key=lambda item: item.vector_score, reverse=True)[:limit]

    def hybrid_search(self, query: str, limit: int = 6) -> list[RetrievedChunk]:
        combined: dict[str, RetrievedChunk] = {}

        for result in self.keyword_search(query, limit=limit * 3):
            combined[result.chunk.chunk_id] = result

        for result in self.vector_search(query, limit=limit * 3):
            current = combined.get(result.chunk.chunk_id)
            if current:
                combined[result.chunk.chunk_id] = RetrievedChunk(
                    chunk=current.chunk,
                    score=current.keyword_score + result.vector_score,
                    keyword_score=current.keyword_score,
                    vector_score=result.vector_score,
                )
            else:
                combined[result.chunk.chunk_id] = result

        return sorted(combined.values(), key=lambda item: item.score, reverse=True)[:limit]

    def stats(self) -> dict[str, object]:
        with self._connect() as connection:
            chunk_count = connection.execute("SELECT COUNT(*) AS count FROM chunks").fetchone()["count"]
            file_count = connection.execute(
                "SELECT COUNT(DISTINCT file_path) AS count FROM chunks"
            ).fetchone()["count"]

        return {
            "files": file_count,
            "chunks": chunk_count,
            "db_path": str(self.db_path),
            "chroma_enabled": bool(self.collection),
            "embedding_provider": self.embedding_provider.name,
        }

    def _chunks_by_chroma_ids(self, ids: list[str], distances: list[float]) -> list[RetrievedChunk]:
        if not ids:
            return []

        placeholders = ",".join("?" for _ in ids)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM chunks WHERE chunk_id IN ({placeholders})",
                ids,
            ).fetchall()

        rows_by_id = {row["chunk_id"]: row for row in rows}
        results = []
        for index, chunk_id in enumerate(ids):
            row = rows_by_id.get(chunk_id)
            if not row:
                continue

            distance = distances[index] if index < len(distances) else 1.0
            vector_score = 1.0 / (1.0 + max(float(distance), 0.0))
            results.append(
                RetrievedChunk(
                    chunk=self._row_to_chunk(row),
                    score=vector_score,
                    keyword_score=0.0,
                    vector_score=vector_score,
                )
            )
        return results

    @staticmethod
    def _to_fts_query(query: str) -> str:
        tokens = re.findall(r"[\wÀ-ÿ]{2,}", query.lower())
        return " OR ".join(f'"{token}"' for token in tokens[:12])

    @staticmethod
    def _row_to_chunk(row: sqlite3.Row) -> DocumentChunk:
        return DocumentChunk(
            chunk_id=row["chunk_id"],
            file_path=row["file_path"],
            filename=row["filename"],
            page_number=row["page_number"],
            year=row["year"],
            text=row["text"],
            embedding=json.loads(row["embedding_json"] or "[]"),
        )
