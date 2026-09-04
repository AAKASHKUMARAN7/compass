"""ChromaDB persistence for policy chunks.

Chroma is used directly rather than through a framework wrapper so that
embedding calls, metadata filters and distance-to-similarity conversion stay
explicit and testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import Settings
from app.core.logging import get_logger
from app.services.embeddings import EmbeddingBackend
from app.services.ingestion import Chunk
from app.services.lexical import LexicalIndex, query_variants

logger = get_logger(__name__)

_EMBED_BATCH = 64


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    text: str
    score: float
    metadata: dict[str, Any]
    vector_score: float = 0.0
    lexical_score: float = 0.0
    matched_by: str = "vector"

    @property
    def section(self) -> str | None:
        value = self.metadata.get("section")
        return value or None

    @property
    def page(self) -> int | None:
        value = self.metadata.get("page")
        return int(value) if isinstance(value, (int, float)) and value > 0 else None


class VectorStore:
    def __init__(self, settings: Settings, embedder: EmbeddingBackend) -> None:
        self._settings = settings
        self._embedder = embedder
        self._client = chromadb.PersistentClient(
            path=str(settings.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False),
        )
        # The collection is namespaced by embedding model: switching providers
        # produces an incompatible vector space, and silently mixing them would
        # corrupt retrieval quality in ways that are very hard to diagnose.
        self._collection_name = f"{settings.chroma_collection}__{_slug(embedder.model)}"
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine", "embedding_model": embedder.model},
        )
        self._lexical = LexicalIndex()
        self._rebuild_lexical_index()
        logger.info(
            "vector_store_ready collection=%s count=%d lexical_terms=%d",
            self._collection_name,
            self.count(),
            len(self._lexical),
        )

    def _rebuild_lexical_index(self) -> None:
        """Reconstruct the in-memory term index from the persisted chunks."""
        try:
            result = self._collection.get(include=["documents", "metadatas"])
        except Exception as exc:  # pragma: no cover - storage level failure
            logger.error("lexical_index_rebuild_failed error=%s", exc)
            return

        self._lexical.clear()
        for chunk_id, text, metadata in zip(
            result.get("ids") or [],
            result.get("documents") or [],
            result.get("metadatas") or [],
        ):
            self._lexical.add(chunk_id, str((metadata or {}).get("document_id", "")), text or "")

    @property
    def collection_name(self) -> str:
        return self._collection_name

    def count(self) -> int:
        try:
            return self._collection.count()
        except Exception as exc:  # pragma: no cover - storage level failure
            logger.error("vector_store_count_failed error=%s", exc)
            return 0

    # -- writes -----------------------------------------------------------

    def add_chunks(
        self, document_id: str, chunks: Sequence[Chunk], base_metadata: dict[str, Any]
    ) -> int:
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for chunk in chunks:
            ids.append(f"{document_id}::{chunk.ordinal}")
            documents.append(chunk.text)
            metadatas.append(
                {
                    **base_metadata,
                    "document_id": document_id,
                    "ordinal": chunk.ordinal,
                    "section": chunk.section or "",
                    "page": chunk.page or 0,
                }
            )

        for start in range(0, len(ids), _EMBED_BATCH):
            stop = start + _EMBED_BATCH
            vectors = self._embedder.embed_documents(documents[start:stop])
            self._collection.upsert(
                ids=ids[start:stop],
                documents=documents[start:stop],
                metadatas=metadatas[start:stop],
                embeddings=vectors,
            )

        for chunk_id, text in zip(ids, documents):
            self._lexical.add(chunk_id, document_id, text)

        logger.info("chunks_indexed document_id=%s count=%d", document_id, len(ids))
        return len(ids)

    def update_document_metadata(self, document_id: str, fields: dict[str, Any]) -> None:
        result = self._collection.get(where={"document_id": document_id}, include=["metadatas"])
        ids = result.get("ids") or []
        if not ids:
            return
        metadatas = [{**(meta or {}), **fields} for meta in (result.get("metadatas") or [])]
        self._collection.update(ids=ids, metadatas=metadatas)

    def delete_document(self, document_id: str) -> None:
        self._collection.delete(where={"document_id": document_id})
        self._lexical.remove_document(document_id)
        logger.info("chunks_deleted document_id=%s", document_id)

    # -- reads ------------------------------------------------------------

    def get_document_chunks(self, document_id: str, limit: int = 25) -> list[RetrievedChunk]:
        result = self._collection.get(
            where={"document_id": document_id},
            include=["documents", "metadatas"],
            limit=limit,
        )
        chunks = [
            RetrievedChunk(
                chunk_id=chunk_id,
                document_id=document_id,
                text=text,
                score=1.0,
                metadata=metadata or {},
            )
            for chunk_id, text, metadata in zip(
                result.get("ids") or [],
                result.get("documents") or [],
                result.get("metadatas") or [],
            )
        ]
        chunks.sort(key=lambda item: item.metadata.get("ordinal", 0))
        return chunks

    def search(
        self,
        query: str,
        *,
        top_k: int,
        allowed_document_ids: Iterable[str] | None = None,
        category: str | None = None,
        jurisdiction: str | None = None,
    ) -> list[RetrievedChunk]:
        """Hybrid search over the documents the reader may see.

        Dense retrieval supplies paraphrase tolerance; the lexical index
        supplies robustness to morphology and rare terms that the embedding
        model handles badly. Candidates from both are fused on a single [0, 1]
        scale so one calibrated relevance floor still governs the gate.
        """
        where = self._build_filter(allowed_document_ids, category, jurisdiction)
        if where is None:
            return []

        allowed = set(allowed_document_ids) if allowed_document_ids is not None else None

        # Over-fetch from both arms: fusion re-ranks, so the final top_k should
        # be chosen after merging rather than by either arm alone.
        fetch = max(top_k * 2, top_k + 4)
        candidates = self._vector_candidates(query, fetch, where)
        self._merge_lexical(query, candidates, fetch, allowed, category, jurisdiction)

        ranked = sorted(candidates.values(), key=lambda chunk: chunk.score, reverse=True)
        return ranked[:top_k]

    def _vector_candidates(
        self, query: str, fetch: int, where: dict[str, Any]
    ) -> dict[str, RetrievedChunk]:
        """Dense retrieval over the query and its normalised variants.

        Each variant is embedded and searched, and a chunk keeps the best
        similarity any variant achieved. Taking the maximum means normalisation
        can only rescue a query the model mishandles -- it can never make a
        well-formed question score worse.
        """
        variants = query_variants(query)
        try:
            result = self._collection.query(
                query_embeddings=[self._embedder.embed_query(v) for v in variants],
                n_results=fetch,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:  # pragma: no cover - storage level failure
            logger.error("vector_search_failed error=%s", exc)
            return {}

        candidates: dict[str, RetrievedChunk] = {}
        for index in range(len(variants)):
            for chunk_id, text, metadata, distance in zip(
                (result.get("ids") or [[]])[index],
                (result.get("documents") or [[]])[index],
                (result.get("metadatas") or [[]])[index],
                (result.get("distances") or [[]])[index],
            ):
                metadata = metadata or {}
                similarity = _cosine_similarity(distance)
                existing = candidates.get(chunk_id)
                if existing is not None:
                    if similarity > existing.vector_score:
                        existing.vector_score = similarity
                        existing.score = similarity
                    continue
                candidates[chunk_id] = RetrievedChunk(
                    chunk_id=chunk_id,
                    document_id=str(metadata.get("document_id", "")),
                    text=text,
                    score=similarity,
                    metadata=metadata,
                    vector_score=similarity,
                    matched_by="vector",
                )
        return candidates

    def _merge_lexical(
        self,
        query: str,
        candidates: dict[str, RetrievedChunk],
        fetch: int,
        allowed: set[str] | None,
        category: str | None,
        jurisdiction: str | None = None,
    ) -> None:
        """Fuse lexical coverage into the candidate set, pulling in new chunks."""
        lexical_hits = self._lexical.top_chunk_ids(
            query, limit=fetch, allowed_document_ids=allowed
        )
        if not lexical_hits:
            return

        missing = [chunk_id for chunk_id, _ in lexical_hits if chunk_id not in candidates]
        fetched = self._fetch_by_ids(missing) if missing else {}

        for chunk_id, lexical_score in lexical_hits:
            existing = candidates.get(chunk_id)

            if existing is None:
                record = fetched.get(chunk_id)
                if record is None:
                    continue
                text, metadata = record
                # The vector arm applies its filter in the query; chunks reached
                # only through the lexical index must be filtered here.
                if category and str(metadata.get("category", "")) != category:
                    continue
                if jurisdiction and str(
                    metadata.get("jurisdiction", "global")
                ) not in (jurisdiction, "global"):
                    continue
                existing = RetrievedChunk(
                    chunk_id=chunk_id,
                    document_id=str(metadata.get("document_id", "")),
                    text=text,
                    score=0.0,
                    metadata=metadata,
                    vector_score=0.0,
                    matched_by="lexical",
                )
                candidates[chunk_id] = existing

            existing.lexical_score = lexical_score
            fused = self._fuse(existing.vector_score, lexical_score)
            if fused > existing.score:
                existing.score = fused
                if lexical_score > existing.vector_score:
                    existing.matched_by = (
                        "lexical" if existing.vector_score == 0.0 else "hybrid"
                    )

    def _fetch_by_ids(self, chunk_ids: list[str]) -> dict[str, tuple[str, dict[str, Any]]]:
        try:
            result = self._collection.get(
                ids=chunk_ids, include=["documents", "metadatas"]
            )
        except Exception as exc:  # pragma: no cover - storage level failure
            logger.error("chunk_fetch_failed error=%s", exc)
            return {}

        return {
            chunk_id: (text or "", metadata or {})
            for chunk_id, text, metadata in zip(
                result.get("ids") or [],
                result.get("documents") or [],
                result.get("metadatas") or [],
            )
        }

    @staticmethod
    def _build_filter(
        allowed_document_ids: Iterable[str] | None,
        category: str | None,
        jurisdiction: str | None = None,
    ) -> dict[str, Any] | None:
        """Compose the metadata constraints a chunk must satisfy to be a candidate.

        Scoping lives here rather than in the UI on purpose: a reader can never
        be cited a document that was never a retrieval candidate. The same
        clause list is where a document-level ACL belongs.
        """
        clauses: list[dict[str, Any]] = []

        if allowed_document_ids is not None:
            allowed = list(allowed_document_ids)
            if not allowed:
                return None  # nothing published -> no results, skip the round trip
            clauses.append({"document_id": {"$in": allowed}})

        if category:
            clauses.append({"category": category})

        if jurisdiction:
            # A reader sees their own entity's rules plus the firm-wide baseline,
            # and never another entity's.
            clauses.append({"jurisdiction": {"$in": [jurisdiction, "global"]}})

        if not clauses:
            return {}
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}


    def _fuse(self, vector_score: float, lexical_score: float) -> float:
        """Combine the two retrieval signals onto one [0, 1] scale.

        The blend is taken as a maximum against the raw vector score, so adding
        the lexical arm can only ever rescue a chunk, never demote one that
        dense retrieval already ranked highly. That keeps the relevance floor
        calibrated on the vector distribution valid.
        """
        weight = self._settings.lexical_weight
        blended = (1.0 - weight) * vector_score + weight * lexical_score
        return max(vector_score, blended)


def _cosine_similarity(distance: float | None) -> float:
    """Chroma returns cosine distance in [0, 2]; convert to similarity in [0, 1]."""
    if distance is None:
        return 0.0
    return max(0.0, min(1.0, 1.0 - float(distance)))


def _slug(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value.lower()).strip("_")
