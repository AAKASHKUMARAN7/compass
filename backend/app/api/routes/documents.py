"""Document management endpoints (administrator surface)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from pydantic import ValidationError as PydanticValidationError

from app.core.errors import AppError
from app.dependencies import get_document_service
from app.schemas.common import DocumentStatus, Page, PolicyCategory
from app.schemas.documents import (
    DocumentDetail,
    DocumentMetadataForm,
    DocumentRecord,
    DocumentStatusUpdate,
    IngestionResult,
)
from app.services.documents import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


class _FormValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_error"


@router.post(
    "",
    response_model=IngestionResult,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and index a policy document",
)
async def upload_document(
    file: UploadFile = File(..., description="PDF, TXT or Markdown policy document"),
    title: str = Form(...),
    owner: str = Form(...),
    category: PolicyCategory = Form(PolicyCategory.OTHER),
    version_label: str = Form("v1.0"),
    effective_date: date | None = Form(None),
    summary: str | None = Form(None),
    service: DocumentService = Depends(get_document_service),
) -> IngestionResult:
    """Parse, chunk, embed and publish a document in a single request.

    Multipart fields are validated through the same Pydantic model used
    elsewhere so form and JSON inputs cannot drift apart.
    """
    try:
        metadata = DocumentMetadataForm(
            title=title,
            owner=owner,
            category=category,
            version_label=version_label,
            effective_date=effective_date,
            summary=summary,
        )
    except PydanticValidationError as exc:
        first = exc.errors()[0]
        field = ".".join(str(part) for part in first.get("loc", [])) or "form"
        raise _FormValidationError(
            "Invalid value for field: " + field, detail=first.get("msg")
        ) from exc

    payload = await file.read()
    return service.ingest(
        payload=payload,
        filename=file.filename or "document",
        content_type=file.content_type,
        metadata=metadata,
    )


@router.get("", response_model=Page[DocumentRecord], summary="List policy documents")
async def list_documents(
    status_filter: DocumentStatus | None = Query(None, alias="status"),
    category: PolicyCategory | None = Query(None),
    search: str | None = Query(None, max_length=120),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: DocumentService = Depends(get_document_service),
) -> Page[DocumentRecord]:
    items, total = service.list_documents(
        status=status_filter.value if status_filter else None,
        category=category.value if category else None,
        search=search,
        limit=limit,
        offset=offset,
    )
    return Page[DocumentRecord](items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/{document_id}",
    response_model=DocumentDetail,
    summary="Inspect a document and its indexed chunks",
)
async def get_document(
    document_id: str,
    service: DocumentService = Depends(get_document_service),
) -> DocumentDetail:
    return service.get_document(document_id)


@router.patch(
    "/{document_id}/status",
    response_model=DocumentRecord,
    summary="Publish or archive a document",
)
async def update_status(
    document_id: str,
    payload: DocumentStatusUpdate,
    service: DocumentService = Depends(get_document_service),
) -> DocumentRecord:
    """Archiving removes a document from retrieval without destroying it."""
    return service.set_status(document_id, payload.status)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a document and its embeddings",
)
async def delete_document(
    document_id: str,
    service: DocumentService = Depends(get_document_service),
) -> Response:
    service.delete(document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
