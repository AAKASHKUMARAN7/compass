"""Operational analytics.

The point of this module is the coverage-gap report: every question the
assistant refused becomes a prioritised content task for the policy owner. That
turns the failure mode of a RAG system into the product's feedback loop.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from app.core.logging import get_logger
from app.schemas.analytics import (
    AnalyticsOverview,
    CategoryBreakdown,
    CoverageGap,
    KpiSummary,
    TopQuestion,
)
from app.schemas.common import PolicyCategory
from app.services.registry import MetadataRegistry
from app.services.vectorstore import VectorStore

logger = get_logger(__name__)


class AnalyticsService:
    def __init__(self, registry: MetadataRegistry, store: VectorStore) -> None:
        self._registry = registry
        self._store = store

    def overview(self) -> AnalyticsOverview:
        documents = self._registry.list_documents()
        queries = self._registry.all_queries()

        published = [d for d in documents if d.get("status") == "published"]
        archived = [d for d in documents if d.get("status") == "archived"]

        answered = [q for q in queries if q.get("status") == "answered"]
        gaps = [q for q in queries if q.get("status") != "answered"]

        rated = [q for q in queries if q.get("feedback")]
        helpful = [q for q in rated if q.get("feedback") == "helpful"]

        kpis = KpiSummary(
            documents_published=len(published),
            documents_archived=len(archived),
            chunks_indexed=self._store.count(),
            questions_asked=len(queries),
            answer_rate=round(len(answered) / len(queries), 4) if queries else 0.0,
            coverage_gap_count=len(gaps),
            avg_confidence_score=round(
                sum(float(q.get("top_score", 0.0)) for q in answered) / len(answered), 4
            )
            if answered
            else 0.0,
            avg_latency_ms=int(
                sum(int(q.get("latency_ms", 0)) for q in queries) / len(queries)
            )
            if queries
            else 0,
            helpful_rate=round(len(helpful) / len(rated), 4) if rated else None,
        )

        return AnalyticsOverview(
            kpis=kpis,
            categories=self._categories(documents, queries),
            coverage_gaps=self._coverage_gaps(gaps),
            top_questions=self._top_questions(answered),
            generated_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _categories(documents: list[dict], queries: list[dict]) -> list[CategoryBreakdown]:
        doc_counts: dict[str, int] = defaultdict(int)
        for document in documents:
            if document.get("status") == "published":
                doc_counts[str(document.get("category", "other"))] += 1

        query_counts: dict[str, int] = defaultdict(int)
        for query in queries:
            category = query.get("category")
            if category:
                query_counts[str(category)] += 1

        rows: list[CategoryBreakdown] = []
        for category in {*doc_counts, *query_counts}:
            try:
                enum_value = PolicyCategory(category)
            except ValueError:
                enum_value = PolicyCategory.OTHER
            rows.append(
                CategoryBreakdown(
                    category=enum_value,
                    document_count=doc_counts.get(category, 0),
                    question_count=query_counts.get(category, 0),
                )
            )

        rows.sort(key=lambda row: (row.document_count, row.question_count), reverse=True)
        return rows

    @staticmethod
    def _coverage_gaps(gaps: list[dict]) -> list[CoverageGap]:
        buckets: dict[str, list[dict]] = defaultdict(list)
        for gap in gaps:
            buckets[_normalise(gap.get("question", ""))].append(gap)

        rows: list[CoverageGap] = []
        for entries in buckets.values():
            if not entries:
                continue
            latest = max(entries, key=lambda item: str(item.get("created_at", "")))
            rows.append(
                CoverageGap(
                    question=str(latest.get("question", "")),
                    occurrences=len(entries),
                    best_score=round(
                        max(float(item.get("top_score", 0.0)) for item in entries), 4
                    ),
                    last_asked_at=_parse_dt(latest.get("created_at")),
                )
            )

        # Most-repeated first: frequency is the signal for what to write next.
        rows.sort(key=lambda row: (row.occurrences, row.last_asked_at), reverse=True)
        return rows[:15]

    @staticmethod
    def _top_questions(answered: list[dict]) -> list[TopQuestion]:
        buckets: dict[str, list[dict]] = defaultdict(list)
        for query in answered:
            buckets[_normalise(query.get("question", ""))].append(query)

        rows = [
            TopQuestion(
                question=str(entries[-1].get("question", "")),
                occurrences=len(entries),
                avg_score=round(
                    sum(float(item.get("top_score", 0.0)) for item in entries) / len(entries),
                    4,
                ),
            )
            for entries in buckets.values()
            if entries
        ]
        rows.sort(key=lambda row: row.occurrences, reverse=True)
        return rows[:10]


def _normalise(question: str) -> str:
    return " ".join(question.lower().split()).rstrip("?.! ")


def _parse_dt(value: object) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now(timezone.utc)
