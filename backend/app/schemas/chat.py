"""Assistant question/answer contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import AnswerStatus, Confidence, FeedbackRating, PolicyCategory


class AskRequest(BaseModel):
    question: str = Field(..., min_length=8, max_length=500)
    category: PolicyCategory | None = Field(
        None, description="Optional filter to restrict retrieval to one policy area."
    )
    asked_by: str = Field("employee@company.com", max_length=120)

    @field_validator("question")
    @classmethod
    def _normalise(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 8:
            raise ValueError("Question must be at least 8 characters.")
        return cleaned


class Citation(BaseModel):
    marker: int = Field(..., description="Matches the [n] marker used in the answer body.")
    chunk_id: str
    document_id: str
    document_title: str
    section: str | None
    page: int | None
    version_label: str
    owner: str
    effective_date: str | None
    relevance: float = Field(..., ge=0.0, le=1.0)
    excerpt: str


class AskResponse(BaseModel):
    query_id: str
    question: str
    status: AnswerStatus
    answer: str
    confidence: Confidence
    top_score: float
    citations: list[Citation]
    follow_up_questions: list[str] = []
    generation_mode: str
    model: str | None
    latency_ms: int
    created_at: datetime


class QueryLogEntry(BaseModel):
    id: str
    question: str
    status: AnswerStatus
    confidence: Confidence
    top_score: float
    category: PolicyCategory | None
    asked_by: str
    citation_count: int
    latency_ms: int
    feedback: FeedbackRating | None
    created_at: datetime


class FeedbackRequest(BaseModel):
    rating: FeedbackRating
    comment: str | None = Field(None, max_length=400)
