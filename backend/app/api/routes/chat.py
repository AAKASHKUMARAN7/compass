"""Assistant endpoints (employee surface)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.errors import NotFoundError
from app.dependencies import get_rag_service, get_registry
from app.schemas.chat import AskRequest, AskResponse, FeedbackRequest, QueryLogEntry
from app.schemas.common import Page
from app.services.rag import RagService
from app.services.registry import MetadataRegistry

router = APIRouter(prefix="/chat", tags=["assistant"])


@router.post(
    "/ask",
    response_model=AskResponse,
    summary="Ask a policy question and receive a cited answer",
)
async def ask(
    payload: AskRequest,
    service: RagService = Depends(get_rag_service),
) -> AskResponse:
    """Answer strictly from published policy content.

    When retrieval evidence is too weak the response comes back with
    ``status = no_coverage`` and no citations rather than a speculative answer.
    """
    return service.ask(payload)


@router.get(
    "/history",
    response_model=Page[QueryLogEntry],
    summary="Recent questions asked of the assistant",
)
async def history(
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    registry: MetadataRegistry = Depends(get_registry),
) -> Page[QueryLogEntry]:
    rows, total = registry.list_queries(limit=limit, offset=offset)
    items = [
        QueryLogEntry(
            id=row["id"],
            question=row["question"],
            status=row["status"],
            confidence=row["confidence"],
            top_score=row.get("top_score", 0.0),
            category=row.get("category"),
            asked_by=row.get("asked_by", "unknown"),
            citation_count=row.get("citation_count", 0),
            latency_ms=row.get("latency_ms", 0),
            feedback=row.get("feedback"),
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return Page[QueryLogEntry](items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/{query_id}/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Record whether an answer was useful",
)
async def submit_feedback(
    query_id: str,
    payload: FeedbackRequest,
    registry: MetadataRegistry = Depends(get_registry),
) -> Response:
    """Feedback is the ground truth that ranks the content backlog."""
    updated = registry.set_query_feedback(query_id, payload.rating.value, payload.comment)
    if updated is None:
        raise NotFoundError(f"Query '{query_id}' was not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
