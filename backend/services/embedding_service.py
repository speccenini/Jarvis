"""Pluggable embedding providers for local document retrieval."""

from __future__ import annotations

import hashlib
import math
import os
import re
from dataclasses import dataclass


class EmbeddingError(Exception):
    """Raised when embeddings cannot be created."""


class EmbeddingProvider:
    """Small interface used by the indexing and retrieval services."""

    name = "base"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]


@dataclass
class HashingEmbeddingProvider(EmbeddingProvider):
    """Deterministic local fallback.

    This is lexical rather than truly semantic, but it keeps the whole RAG
    pipeline operational without external services. Replacing it only requires
    swapping the provider.
    """

    dimensions: int = 384
    name = "local_hashing"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"[\wÀ-ÿ]{2,}", text.lower())

        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if not norm:
            return vector
        return [value / norm for value in vector]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider, loaded lazily so the dependency is optional."""

    name = "openai"

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise EmbeddingError("OPENAI_API_KEY is not configured.")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise EmbeddingError("Install the openai package to use OpenAI embeddings.") from exc

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        response = self.client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]


def build_embedding_provider(
    provider_name: str = "auto",
    openai_api_key: str | None = None,
    openai_model: str = "text-embedding-3-small",
) -> EmbeddingProvider:
    """Create an embedding provider from configuration."""

    normalized = (provider_name or "auto").lower()
    api_key = openai_api_key if openai_api_key is not None else os.getenv("OPENAI_API_KEY", "")

    if normalized in {"openai", "auto"} and api_key:
        try:
            return OpenAIEmbeddingProvider(api_key=api_key, model=openai_model)
        except EmbeddingError:
            if normalized == "openai":
                raise

    if normalized in {"auto", "hashing", "local", "local_hashing"}:
        return HashingEmbeddingProvider()

    raise EmbeddingError(f"Unknown embedding provider: {provider_name}")


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))
