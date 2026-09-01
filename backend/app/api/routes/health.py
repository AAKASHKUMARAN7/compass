"""Health and readiness."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.dependencies import ServiceContainer, get_container
from app.schemas.common import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Service and model status")
async def health(container: ServiceContainer = Depends(get_container)) -> HealthResponse:
    """Reports which providers actually resolved at startup.

    The frontend renders this as a status banner so a degraded configuration
    (no API key, fallback embeddings) is visible rather than silent.
    """
    stats = container.registry.stats()
    return HealthResponse(
        status="ok",
        version=container.settings.app_version,
        environment=container.settings.environment,
        llm_provider=container.generator.provider,
        llm_model=container.generator.model_name,
        embedding_provider=container.embedder.name,
        embedding_model=container.embedder.model,
        generation_mode=container.generator.effective_mode,
        generation_detail=container.generator.last_error,
        documents_published=stats["documents_published"],
        chunks_indexed=container.store.count(),
        checked_at=datetime.now(timezone.utc),
    )
