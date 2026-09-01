"""Embedding providers.

Chroma is given an explicit embedding function rather than its implicit default
so the vector space is a deliberate, logged choice. Provider resolution
degrades in a defined order:

    configured provider -> local ONNX model -> deterministic hashed bag-of-words

The final tier keeps the product demonstrable on a machine with no API key and
no model download; retrieval quality drops to lexical matching and the service
reports the degraded mode through /api/health.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol, Sequence

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9']+")


class EmbeddingBackend(Protocol):
    name: str
    model: str

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class HashingEmbedding:
    """Deterministic offline fallback.

    Projects a normalised bag-of-words into a fixed-width vector with sublinear
    term weighting. Not semantic, but stable, dependency-free and good enough
    for keyword-level recall so the application remains usable offline.
    """

    name = "hashing-fallback"
    model = "hashing-1024"
    dimensions = 1024

    def _vector(self, text: str) -> list[float]:
        counts: dict[int, float] = {}
        for token in _TOKEN_RE.findall(text.lower()):
            if len(token) < 2:
                continue
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            counts[index] = counts.get(index, 0.0) + sign

        vector = [0.0] * self.dimensions
        for index, raw in counts.items():
            vector[index] = math.copysign(1.0 + math.log1p(abs(raw)), raw)

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


class LangChainEmbedding:
    """Adapter over a LangChain embeddings implementation."""

    def __init__(self, name: str, model: str, delegate) -> None:
        self.name = name
        self.model = model
        self._delegate = delegate

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._delegate.embed_documents(list(texts))

    def embed_query(self, text: str) -> list[float]:
        return self._delegate.embed_query(text)


def _build_google(settings: Settings) -> EmbeddingBackend | None:
    if not settings.google_api_key:
        return None
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        delegate = GoogleGenerativeAIEmbeddings(
            model=settings.google_embedding_model,
            google_api_key=settings.google_api_key,
        )
        # Fail fast at startup rather than on the first user question.
        delegate.embed_query("connectivity probe")
        return LangChainEmbedding("google", settings.google_embedding_model, delegate)
    except Exception as exc:
        logger.warning("embedding_provider_unavailable provider=google error=%s", exc)
        return None


def _build_openai(settings: Settings) -> EmbeddingBackend | None:
    if not settings.openai_api_key:
        return None
    try:
        from langchain_openai import OpenAIEmbeddings

        delegate = OpenAIEmbeddings(
            model=settings.openai_embedding_model,
            api_key=settings.openai_api_key,
        )
        delegate.embed_query("connectivity probe")
        return LangChainEmbedding("openai", settings.openai_embedding_model, delegate)
    except Exception as exc:
        logger.warning("embedding_provider_unavailable provider=openai error=%s", exc)
        return None


def _build_local() -> EmbeddingBackend | None:
    """Chroma's bundled MiniLM ONNX model. Downloads once, then works offline."""
    try:
        from chromadb.utils import embedding_functions

        fn = embedding_functions.ONNXMiniLM_L6_V2()
        # The ONNX function returns numpy arrays; use explicit length checks
        # rather than truthiness, which is ambiguous for arrays.
        probe = fn(["connectivity probe"])
        if len(probe) == 0 or len(probe[0]) == 0:
            raise RuntimeError("empty embedding returned")

        def _to_floats(vector) -> list[float]:
            # Chroma rejects numpy scalars inside a plain list, so normalise to
            # native floats regardless of what the backend hands back.
            tolist = getattr(vector, "tolist", None)
            return [float(value) for value in (tolist() if tolist else vector)]

        class _Local:
            name = "local"
            model = "all-MiniLM-L6-v2"

            def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
                return [_to_floats(vector) for vector in fn(list(texts))]

            def embed_query(self, text: str) -> list[float]:
                return _to_floats(fn([text])[0])

        return _Local()
    except Exception as exc:
        logger.warning("embedding_provider_unavailable provider=local error=%s", exc)
        return None


def build_embedding_backend(settings: Settings) -> EmbeddingBackend:
    """Resolve the best available embedding backend for this process."""
    order: list[str] = []
    if settings.embedding_provider == "google":
        order = ["google", "openai", "local"]
    elif settings.embedding_provider == "openai":
        order = ["openai", "google", "local"]
    else:
        order = ["local", "google", "openai"]

    for provider in order:
        backend: EmbeddingBackend | None = None
        if provider == "google":
            backend = _build_google(settings)
        elif provider == "openai":
            backend = _build_openai(settings)
        elif provider == "local":
            backend = _build_local()

        if backend is not None:
            logger.info("embedding_backend_selected provider=%s model=%s", backend.name, backend.model)
            return backend

    logger.warning("embedding_backend_degraded reason=no_provider_available")
    return HashingEmbedding()
