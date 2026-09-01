"""API route modules."""

from fastapi import APIRouter

from app.api.routes import analytics, chat, documents, health

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(documents.router)
api_router.include_router(chat.router)
api_router.include_router(analytics.router)

__all__ = ["api_router"]
