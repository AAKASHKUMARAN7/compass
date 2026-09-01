"""Composition root.

Services are constructed once at application startup and handed to routes via
FastAPI dependencies, so handlers stay free of construction logic and the whole
graph can be swapped for fakes in a test.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.analytics import AnalyticsService
from app.services.documents import DocumentService
from app.services.embeddings import EmbeddingBackend, build_embedding_backend
from app.services.llm import AnswerGenerator
from app.services.rag import RagService
from app.services.registry import MetadataRegistry
from app.services.vectorstore import VectorStore

logger = get_logger(__name__)


@dataclass
class ServiceContainer:
    settings: Settings
    embedder: EmbeddingBackend
    registry: MetadataRegistry
    store: VectorStore
    generator: AnswerGenerator
    documents: DocumentService
    rag: RagService
    analytics: AnalyticsService


def build_container(settings: Settings | None = None) -> ServiceContainer:
    settings = settings or get_settings()

    embedder = build_embedding_backend(settings)
    registry = MetadataRegistry(settings.registry_path)
    store = VectorStore(settings, embedder)
    generator = AnswerGenerator(settings)

    container = ServiceContainer(
        settings=settings,
        embedder=embedder,
        registry=registry,
        store=store,
        generator=generator,
        documents=DocumentService(settings, store, registry),
        rag=RagService(settings, store, generator, registry),
        analytics=AnalyticsService(registry, store),
    )
    logger.info(
        "container_ready embedding=%s llm_mode=%s collection=%s",
        embedder.name,
        generator.mode,
        store.collection_name,
    )
    return container


def get_container(request: Request) -> ServiceContainer:
    return request.app.state.container


def get_document_service(
    container: ServiceContainer = Depends(get_container),
) -> DocumentService:
    return container.documents


def get_rag_service(container: ServiceContainer = Depends(get_container)) -> RagService:
    return container.rag


def get_analytics_service(
    container: ServiceContainer = Depends(get_container),
) -> AnalyticsService:
    return container.analytics


def get_registry(container: ServiceContainer = Depends(get_container)) -> MetadataRegistry:
    return container.registry
