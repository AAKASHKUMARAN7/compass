"""Operational analytics contracts.

These power the admin view that turns unanswered questions into a content
backlog for the policy owners.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import PolicyCategory


class KpiSummary(BaseModel):
    documents_published: int
    documents_archived: int
    chunks_indexed: int
    questions_asked: int
    answer_rate: float
    coverage_gap_count: int
    avg_confidence_score: float
    avg_latency_ms: int
    helpful_rate: float | None


class CategoryBreakdown(BaseModel):
    category: PolicyCategory
    document_count: int
    question_count: int


class CoverageGap(BaseModel):
    question: str
    occurrences: int
    best_score: float
    last_asked_at: datetime


class TopQuestion(BaseModel):
    question: str
    occurrences: int
    avg_score: float


class AnalyticsOverview(BaseModel):
    kpis: KpiSummary
    categories: list[CategoryBreakdown]
    coverage_gaps: list[CoverageGap]
    top_questions: list[TopQuestion]
    generated_at: datetime
