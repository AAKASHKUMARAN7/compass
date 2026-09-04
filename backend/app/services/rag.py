"""Retrieval-augmented answering pipeline.

Flow: retrieve -> gate on relevance -> generate -> bind citations -> log.

The gate is the product decision that makes this safe to put in front of
employees. An assistant that answers "how much parental leave do I get" from a
weak match is worse than one that says it does not know, because a confident
wrong answer about entitlements creates real liability. Questions that fail the
gate are logged as coverage gaps and surfaced to the policy owner as a backlog.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from app.config import Settings
from app.core.logging import get_logger
from app.schemas.chat import AskRequest, AskResponse, Citation
from app.schemas.common import AnswerStatus, Confidence
from app.services.llm import AnswerGenerator
from app.services.registry import MetadataRegistry
from app.services.vectorstore import RetrievedChunk, VectorStore

logger = get_logger(__name__)

_NO_COVERAGE_MESSAGE = (
    "I could not find this in the published policy documents, so I will not guess. "
    "This question has been logged for the policy team to review."
)
_EXCERPT_LIMIT = 420


class RagService:
    def __init__(
        self,
        settings: Settings,
        store: VectorStore,
        generator: AnswerGenerator,
        registry: MetadataRegistry,
    ) -> None:
        self._settings = settings
        self._store = store
        self._generator = generator
        self._registry = registry

    def ask(self, request: AskRequest) -> AskResponse:
        started = time.perf_counter()
        query_id = f"qry_{uuid.uuid4().hex[:12]}"

        published_ids = self._registry.published_document_ids()
        retrieved = self._store.search(
            request.question,
            top_k=self._settings.retrieval_top_k,
            allowed_document_ids=published_ids,
            category=request.category.value if request.category else None,
            jurisdiction=request.jurisdiction.value,
        )

        retrieved = self._apply_jurisdiction_precedence(
            retrieved, request.jurisdiction.value
        )

        top_score = retrieved[0].score if retrieved else 0.0

        if not retrieved or top_score < self._settings.min_relevance_score:
            return self._no_coverage_response(request, query_id, top_score, started)

        generation = self._generator.generate(request.question, retrieved)

        if not generation.answered:
            response = self._no_coverage_response(
                request, query_id, top_score, started, answer=generation.answer
            )
            return response

        citations = self._bind_citations(generation.used_excerpts, retrieved)
        confidence = self._resolve_confidence(generation.confidence, top_score, citations)
        latency_ms = int((time.perf_counter() - started) * 1000)

        response = AskResponse(
            query_id=query_id,
            question=request.question,
            status=AnswerStatus.ANSWERED,
            answer=generation.answer,
            confidence=confidence,
            top_score=round(top_score, 4),
            citations=citations,
            follow_up_questions=generation.follow_up_questions,
            generation_mode=generation.mode,
            model=generation.model,
            latency_ms=latency_ms,
            created_at=datetime.now(timezone.utc),
        )
        self._log(request, response)
        logger.info(
            "question_answered query_id=%s score=%.3f citations=%d confidence=%s latency_ms=%d",
            query_id,
            top_score,
            len(citations),
            confidence.value,
            latency_ms,
        )
        return response

    # -- internals --------------------------------------------------------

    def _no_coverage_response(
        self,
        request: AskRequest,
        query_id: str,
        top_score: float,
        started: float,
        answer: str | None = None,
    ) -> AskResponse:
        latency_ms = int((time.perf_counter() - started) * 1000)
        response = AskResponse(
            query_id=query_id,
            question=request.question,
            status=AnswerStatus.NO_COVERAGE,
            answer=answer or _NO_COVERAGE_MESSAGE,
            confidence=Confidence.NONE,
            top_score=round(top_score, 4),
            citations=[],
            follow_up_questions=[],
            generation_mode=self._generator.mode,
            model=self._generator.model_name,
            latency_ms=latency_ms,
            created_at=datetime.now(timezone.utc),
        )
        self._log(request, response)
        logger.info(
            "coverage_gap query_id=%s score=%.3f question=%r",
            query_id,
            top_score,
            request.question[:120],
        )
        return response

    @staticmethod
    def _apply_jurisdiction_precedence(
        retrieved: list[RetrievedChunk], reader_jurisdiction: str
    ) -> list[RetrievedChunk]:
        """Let a local policy supersede the firm-wide baseline.

        Retrieval returns both the reader's entity policy and the global one,
        and similarity alone does not know which governs -- so a UK reader was
        being handed "25 days ... and 27 days" from two documents at once.
        Policy hierarchies do not work that way: where a jurisdiction has
        published its own rule, that rule replaces the baseline.

        Suppression is scoped to the policy area they actually overlap on, so a
        UK reader asking about expenses still gets the global expense policy
        when no UK-specific one exists.
        """
        if reader_jurisdiction == "global":
            return retrieved

        superseded_categories = {
            str(chunk.metadata.get("category", ""))
            for chunk in retrieved
            if str(chunk.metadata.get("jurisdiction", "global")) == reader_jurisdiction
        }
        if not superseded_categories:
            return retrieved

        kept = [
            chunk
            for chunk in retrieved
            if not (
                str(chunk.metadata.get("jurisdiction", "global")) == "global"
                and str(chunk.metadata.get("category", "")) in superseded_categories
            )
        ]
        dropped = len(retrieved) - len(kept)
        if dropped:
            logger.info(
                "jurisdiction_precedence reader=%s superseded_categories=%s dropped=%d",
                reader_jurisdiction,
                sorted(superseded_categories),
                dropped,
            )
        return kept or retrieved

    def _bind_citations(
        self, used_excerpts: list[int], retrieved: list[RetrievedChunk]
    ) -> list[Citation]:
        """Map model-selected indices onto authoritative source metadata."""
        citations: list[Citation] = []
        for marker in used_excerpts:
            if not 1 <= marker <= len(retrieved):
                continue
            chunk = retrieved[marker - 1]
            metadata = chunk.metadata
            citations.append(
                Citation(
                    marker=marker,
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    document_title=str(metadata.get("document_title", "Untitled document")),
                    section=chunk.section,
                    page=chunk.page,
                    version_label=str(metadata.get("version_label", "")),
                    owner=str(metadata.get("owner", "")),
                    jurisdiction=str(metadata.get("jurisdiction", "global")),
                    effective_date=str(metadata.get("effective_date") or "") or None,
                    relevance=round(chunk.score, 4),
                    excerpt=_truncate(chunk.text),
                )
            )
        return citations

    def _resolve_confidence(
        self, model_confidence: str, top_score: float, citations: list[Citation]
    ) -> Confidence:
        """Reconcile the model's self-report with observable retrieval evidence.

        Self-reported confidence is not trustworthy on its own, so it is capped
        by retrieval score and by whether anything was actually cited.
        """
        if not citations:
            return Confidence.LOW

        evidence = Confidence.HIGH if top_score >= self._settings.high_confidence_score else Confidence.MEDIUM
        if top_score < self._settings.min_relevance_score + 0.08:
            evidence = Confidence.LOW

        claimed = {
            "high": Confidence.HIGH,
            "medium": Confidence.MEDIUM,
            "low": Confidence.LOW,
        }.get(model_confidence, Confidence.MEDIUM)

        rank = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}
        return claimed if rank[claimed] < rank[evidence] else evidence

    def _log(self, request: AskRequest, response: AskResponse) -> None:
        self._registry.append_query(
            {
                "id": response.query_id,
                "question": response.question,
                "status": response.status.value,
                "confidence": response.confidence.value,
                "top_score": response.top_score,
                "category": request.category.value if request.category else None,
                "asked_by": request.asked_by,
                "citation_count": len(response.citations),
                "latency_ms": response.latency_ms,
                "generation_mode": response.generation_mode,
                "feedback": None,
                "feedback_comment": None,
                "created_at": response.created_at.isoformat(),
            }
        )


def _truncate(text: str, limit: int = _EXCERPT_LIMIT) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[:limit].rsplit(" ", 1)[0]
    return cut + "..."
