"""Document lifecycle orchestration.

Owns the transition from an uploaded file to searchable, citable chunks, and
keeps the registry and the vector store consistent with each other.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.core.errors import ConflictError, NotFoundError, PayloadTooLarge
from app.core.logging import get_logger
from app.schemas.common import DocumentStatus
from app.schemas.documents import (
    DocumentChunkPreview,
    DocumentDetail,
    DocumentMetadataForm,
    DocumentRecord,
    DocumentSection,
    IngestionResult,
)
from app.services import ingestion
from app.services.registry import MetadataRegistry
from app.services.vectorstore import VectorStore

logger = get_logger(__name__)

_MUTABLE_STATUSES = {DocumentStatus.PUBLISHED, DocumentStatus.ARCHIVED}


class DocumentService:
    def __init__(
        self, settings: Settings, store: VectorStore, registry: MetadataRegistry
    ) -> None:
        self._settings = settings
        self._store = store
        self._registry = registry

    # -- create -----------------------------------------------------------

    def ingest(
        self,
        *,
        payload: bytes,
        filename: str,
        content_type: str | None,
        metadata: DocumentMetadataForm,
    ) -> IngestionResult:
        started = time.perf_counter()

        if len(payload) > self._settings.max_upload_bytes:
            raise PayloadTooLarge(
                "File exceeds the maximum upload size.",
                detail=f"Limit is {self._settings.max_upload_bytes // (1024 * 1024)} MB.",
            )

        suffix = ingestion.validate_upload(filename, content_type)
        parsed = ingestion.parse_document(payload, suffix)
        chunked = ingestion.chunk_document(
            parsed,
            chunk_size=self._settings.chunk_size,
            chunk_overlap=self._settings.chunk_overlap,
        )

        document_id = f"doc_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        effective_date = metadata.effective_date.isoformat() if metadata.effective_date else None

        record: dict[str, Any] = {
            "id": document_id,
            "title": metadata.title.strip(),
            "category": metadata.category.value,
            "jurisdiction": metadata.jurisdiction.value,
            "owner": metadata.owner.strip(),
            "version_label": metadata.version_label.strip() or "v1.0",
            "effective_date": effective_date,
            "summary": (metadata.summary or "").strip() or None,
            "status": DocumentStatus.PROCESSING.value,
            "filename": filename,
            "content_type": content_type or "application/octet-stream",
            "size_bytes": len(payload),
            "page_count": parsed.page_count,
            "word_count": parsed.word_count,
            "chunk_count": 0,
            "sections": [],
            "failure_reason": None,
            "uploaded_at": now,
            "updated_at": now,
        }
        self._registry.upsert_document(record)

        try:
            indexed = self._store.add_chunks(
                document_id,
                chunked.chunks,
                base_metadata={
                    "document_title": record["title"],
                    "category": record["category"],
                    "jurisdiction": record["jurisdiction"],
                    "owner": record["owner"],
                    "version_label": record["version_label"],
                    "effective_date": effective_date or "",
                },
            )
        except Exception as exc:
            logger.exception("ingestion_failed document_id=%s", document_id)
            self._registry.patch_document(
                document_id,
                status=DocumentStatus.FAILED.value,
                failure_reason=str(exc)[:300],
            )
            raise

        sections = [
            {"label": label, "chunk_count": count} for label, count in chunked.sections[:25]
        ]
        updated = self._registry.patch_document(
            document_id,
            status=DocumentStatus.PUBLISHED.value,
            chunk_count=indexed,
            sections=sections,
        )

        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "document_ingested id=%s chunks=%d words=%d duration_ms=%d",
            document_id,
            indexed,
            parsed.word_count,
            duration_ms,
        )
        return IngestionResult(
            document=_to_record(updated or record),
            chunks_indexed=indexed,
            duration_ms=duration_ms,
        )

    # -- read -------------------------------------------------------------

    def list_documents(
        self,
        *,
        status: str | None,
        category: str | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[DocumentRecord], int]:
        records = self._registry.list_documents(
            status=status, category=category, search=search
        )
        window = records[offset : offset + limit]
        return [_to_record(item) for item in window], len(records)

    def get_document(self, document_id: str) -> DocumentDetail:
        record = self._registry.get_document(document_id)
        if record is None:
            raise NotFoundError(f"Document '{document_id}' was not found.")

        chunks = self._store.get_document_chunks(document_id, limit=20)
        previews = [
            DocumentChunkPreview(
                chunk_id=chunk.chunk_id,
                ordinal=int(chunk.metadata.get("ordinal", index)),
                section=chunk.section,
                page=chunk.page,
                text=chunk.text[:500],
            )
            for index, chunk in enumerate(chunks)
        ]
        return DocumentDetail(**_to_record(record).model_dump(), chunks=previews)

    # -- update / delete --------------------------------------------------

    def set_status(self, document_id: str, status: DocumentStatus) -> DocumentRecord:
        if status not in _MUTABLE_STATUSES:
            raise ConflictError(
                "Status must be either 'published' or 'archived'.",
                detail="'processing' and 'failed' are set by the ingestion pipeline.",
            )

        record = self._registry.get_document(document_id)
        if record is None:
            raise NotFoundError(f"Document '{document_id}' was not found.")
        if record.get("status") == DocumentStatus.FAILED.value:
            raise ConflictError(
                "A failed document cannot be published.",
                detail="Re-upload the file to retry ingestion.",
            )

        updated = self._registry.patch_document(document_id, status=status.value)
        logger.info("document_status_changed id=%s status=%s", document_id, status.value)
        return _to_record(updated or record)

    def delete(self, document_id: str) -> None:
        record = self._registry.get_document(document_id)
        if record is None:
            raise NotFoundError(f"Document '{document_id}' was not found.")

        # Vectors first: an orphaned registry row is recoverable, an orphaned
        # embedding would keep answering questions for a deleted policy.
        self._store.delete_document(document_id)
        self._registry.delete_document(document_id)
        logger.info("document_deleted id=%s", document_id)


def _to_record(raw: dict[str, Any]) -> DocumentRecord:
    data = dict(raw)
    data["sections"] = [
        DocumentSection(**section) if isinstance(section, dict) else section
        for section in data.get("sections", []) or []
    ]
    return DocumentRecord(**data)
