"""Document lifecycle contracts."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import DocumentStatus, Jurisdiction, PolicyCategory


class DocumentMetadataForm(BaseModel):
    """Metadata supplied by the administrator alongside the uploaded file."""

    title: str = Field(..., min_length=3, max_length=160)
    category: PolicyCategory = PolicyCategory.OTHER
    jurisdiction: Jurisdiction = Field(
        Jurisdiction.GLOBAL,
        description="Which entity this governs. 'global' is the firm-wide baseline.",
    )
    owner: str = Field(..., min_length=2, max_length=80)
    version_label: str = Field("v1.0", max_length=32)
    effective_date: date | None = None
    summary: str | None = Field(None, max_length=600)


class DocumentSection(BaseModel):
    label: str
    chunk_count: int


class DocumentRecord(BaseModel):
    id: str
    title: str
    category: PolicyCategory
    jurisdiction: Jurisdiction = Jurisdiction.GLOBAL
    owner: str
    version_label: str
    effective_date: date | None
    summary: str | None
    status: DocumentStatus
    filename: str
    content_type: str
    size_bytes: int
    page_count: int | None
    word_count: int
    chunk_count: int
    sections: list[DocumentSection] = []
    failure_reason: str | None = None
    uploaded_at: datetime
    updated_at: datetime


class DocumentChunkPreview(BaseModel):
    chunk_id: str
    ordinal: int
    section: str | None
    page: int | None
    text: str


class DocumentDetail(DocumentRecord):
    chunks: list[DocumentChunkPreview] = []


class DocumentStatusUpdate(BaseModel):
    status: DocumentStatus = Field(
        ..., description="Only 'published' and 'archived' are accepted."
    )


class IngestionResult(BaseModel):
    document: DocumentRecord
    chunks_indexed: int
    duration_ms: int
