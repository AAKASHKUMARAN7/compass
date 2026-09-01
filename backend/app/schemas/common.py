"""Shared response primitives."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class DocumentStatus(str, Enum):
    PROCESSING = "processing"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    FAILED = "failed"


class PolicyCategory(str, Enum):
    LEAVE_AND_TIME_OFF = "leave_and_time_off"
    COMPENSATION = "compensation"
    BENEFITS = "benefits"
    EXPENSES_AND_TRAVEL = "expenses_and_travel"
    SECURITY_AND_IT = "security_and_it"
    CONDUCT_AND_COMPLIANCE = "conduct_and_compliance"
    WORKPLACE = "workplace"
    OTHER = "other"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class AnswerStatus(str, Enum):
    ANSWERED = "answered"
    NO_COVERAGE = "no_coverage"


class FeedbackRating(str, Enum):
    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"


class Page(BaseModel, Generic[T]):
    """Envelope for list endpoints."""

    items: list[T]
    total: int = Field(..., description="Total records matching the filter")
    limit: int
    offset: int


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    llm_provider: str
    llm_model: str | None
    embedding_provider: str
    embedding_model: str
    generation_mode: str = Field(
        ...,
        description=(
            "'generative' while LLM calls are succeeding, 'degraded' once one has "
            "failed, 'extractive' when no key is configured."
        ),
    )
    generation_detail: str | None = Field(
        None, description="Why generation is degraded, when it is."
    )
    documents_published: int
    chunks_indexed: int
    checked_at: datetime
