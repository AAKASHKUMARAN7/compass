"""Analytics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_analytics_service
from app.schemas.analytics import AnalyticsOverview
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get(
    "/overview",
    response_model=AnalyticsOverview,
    summary="Knowledge-base health, usage and coverage gaps",
)
async def overview(
    service: AnalyticsService = Depends(get_analytics_service),
) -> AnalyticsOverview:
    """Aggregate view used by the operations dashboard."""
    return service.overview()
