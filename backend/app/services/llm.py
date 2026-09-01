"""Answer generation.

Two contracts matter here:

1. The model may only cite numbered contexts it was given. It never supplies
   source metadata itself -- it returns indices, and the service attaches the
   authoritative document title, section and page. A model cannot invent a
   citation it has no way to spell.
2. If the contexts do not support an answer, the model must say so. Refusing is
   a correct outcome for an HR assistant, and the refusal is recorded as a
   content gap for the policy owner.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.config import Settings
from app.core.logging import get_logger
from app.services.vectorstore import RetrievedChunk

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are Compass, the internal policy assistant for an enterprise HR team.
You answer employee questions using ONLY the numbered policy excerpts supplied in the context.

Rules:
1. Ground every factual statement in the excerpts. Never use outside knowledge about typical
   company policy, employment law, or industry norms.
2. Cite excerpts inline using square-bracket markers such as [1] or [2], placed immediately after
   the sentence they support. Cite only excerpt numbers that appear in the context.
3. If the excerpts do not contain the answer, set "answered" to false and explain briefly what is
   missing. Do not guess, and do not offer a partial answer built on assumption.
4. Be concise and direct: two to five sentences for a simple question. Use a short markdown list
   when the policy genuinely enumerates steps, amounts, or conditions.
5. Write for an employee, not a lawyer. Do not restate the question or add pleasantries.
6. Never invent numbers, dates, monetary amounts, or approval names that are not in the excerpts.

Return ONLY a JSON object with this exact shape:
{{
  "answered": boolean,
  "answer": string,
  "used_excerpts": number[],
  "confidence": "high" | "medium" | "low",
  "follow_up_questions": string[]
}}
"follow_up_questions" holds up to three short questions the same employee would plausibly ask
next, each answerable from the same policy area."""
# NOTE: the braces above are doubled on purpose. This string is consumed by a
# LangChain ChatPromptTemplate, which treats single braces as variable slots --
# an unescaped JSON example makes every invocation raise KeyError and silently
# degrade to the extractive fallback.

USER_TEMPLATE = """Employee question:
{question}

Policy excerpts:
{context}

Respond with the JSON object described in your instructions."""


@dataclass
class GenerationResult:
    answered: bool
    answer: str
    used_excerpts: list[int]
    confidence: str
    follow_up_questions: list[str] = field(default_factory=list)
    mode: str = "generative"
    model: str | None = None


class AnswerGenerator:
    """Provider-agnostic answer generation with a deterministic fallback."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._chain = None
        self._model_name: str | None = None
        self._provider = "none"
        # Populated by real traffic, not a startup probe -- see _initialise.
        self._last_error: str | None = None
        self._initialise()

    @property
    def mode(self) -> str:
        return "generative" if self._chain is not None else "extractive"

    @property
    def effective_mode(self) -> str:
        """What the service is actually delivering right now.

        "generative" is only claimed while real calls are succeeding. Once a
        request has failed -- an exhausted quota, a revoked key, an outage --
        this reports "degraded" so the health endpoint and the UI stop
        advertising a capability the user is not getting.
        """
        if self._chain is None:
            return "extractive"
        return "degraded" if self._last_error else "generative"

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model_name(self) -> str | None:
        return self._model_name

    def _initialise(self) -> None:
        settings = self._settings
        if not settings.llm_enabled:
            logger.warning("llm_disabled reason=no_api_key mode=extractive")
            return

        try:
            from langchain_core.prompts import ChatPromptTemplate

            if settings.llm_provider == "google":
                from langchain_google_genai import ChatGoogleGenerativeAI

                model = ChatGoogleGenerativeAI(
                    model=settings.google_chat_model,
                    google_api_key=settings.google_api_key,
                    temperature=settings.llm_temperature,
                    max_output_tokens=settings.llm_max_output_tokens,
                    timeout=settings.llm_timeout_seconds,
                )
                self._model_name = settings.google_chat_model
            else:
                from langchain_openai import ChatOpenAI

                model = ChatOpenAI(
                    model=settings.openai_chat_model,
                    api_key=settings.openai_api_key,
                    temperature=settings.llm_temperature,
                    max_tokens=settings.llm_max_output_tokens,
                    timeout=settings.llm_timeout_seconds,
                )
                self._model_name = settings.openai_chat_model

            # No startup probe. Constructing a client validates nothing, so the
            # honest signal has to come from real traffic -- and on the free
            # tier (20 requests per day per model) a probe on every restart
            # would be a meaningful share of the budget. Instead the first real
            # failure is recorded and reported through /api/health.
            prompt = ChatPromptTemplate.from_messages(
                [("system", SYSTEM_PROMPT), ("human", USER_TEMPLATE)]
            )
            self._chain = prompt | model
            self._provider = settings.llm_provider
            logger.info(
                "llm_ready provider=%s model=%s", settings.llm_provider, self._model_name
            )
        except Exception as exc:
            logger.error(
                "llm_init_failed provider=%s error=%s falling_back=extractive",
                settings.llm_provider,
                exc,
            )
            self._chain = None

    # -- generation -------------------------------------------------------

    def generate(self, question: str, contexts: list[RetrievedChunk]) -> GenerationResult:
        if self._chain is None:
            return self._extractive(question, contexts)

        rendered = self._render_contexts(contexts)
        try:
            response = self._chain.invoke({"question": question, "context": rendered})
            payload = _parse_json_object(getattr(response, "content", str(response)))
        except Exception as exc:
            message = str(exc)
            self._last_error = (
                "Provider quota exhausted" if "429" in message or "quota" in message.lower()
                else f"{type(exc).__name__}: {message[:120]}"
            )
            logger.error("llm_invocation_failed error=%s falling_back=extractive", exc)
            result = self._extractive(question, contexts)
            result.mode = "extractive_fallback"
            return result

        if payload is None:
            self._last_error = "Model returned an unparseable response"
            logger.warning("llm_response_unparseable falling_back=extractive")
            result = self._extractive(question, contexts)
            result.mode = "extractive_fallback"
            return result

        answer = str(payload.get("answer", "")).strip()
        answered = bool(payload.get("answered", bool(answer)))
        if not answer:
            answered = False
            answer = "The published policy documents do not cover this question."

        used = _coerce_indices(payload.get("used_excerpts"), len(contexts))
        # A model that answers without citing anything has not met the contract;
        # fall back to the markers it actually wrote in the prose.
        if answered and not used:
            used = _markers_in_text(answer, len(contexts))

        confidence = str(payload.get("confidence", "medium")).lower()
        if confidence not in {"high", "medium", "low"}:
            confidence = "medium"

        follow_ups = [
            str(item).strip()
            for item in (payload.get("follow_up_questions") or [])
            if str(item).strip()
        ][:3]

        self._last_error = None  # a good call clears a previous degradation
        return GenerationResult(
            answered=answered,
            answer=answer,
            used_excerpts=used,
            confidence=confidence,
            follow_up_questions=follow_ups,
            mode="generative",
            model=self._model_name,
        )

    @staticmethod
    def _render_contexts(contexts: list[RetrievedChunk]) -> str:
        blocks: list[str] = []
        for index, chunk in enumerate(contexts, start=1):
            title = chunk.metadata.get("document_title", "Policy document")
            section = chunk.section or "Unlabelled section"
            page = f", page {chunk.page}" if chunk.page else ""
            blocks.append(
                f"[{index}] Source: {title} — {section}{page}\n{chunk.text.strip()}"
            )
        return "\n\n".join(blocks)

    @staticmethod
    def _extractive(question: str, contexts: list[RetrievedChunk]) -> GenerationResult:
        """Deterministic answer used when no LLM is configured or reachable.

        Selects the sentences with the highest lexical overlap with the question
        so the product stays demonstrable without a provider key. The response is
        labelled 'extractive' end to end so nobody mistakes it for generation.
        """
        if not contexts:
            return GenerationResult(
                answered=False,
                answer="No published policy content matches this question.",
                used_excerpts=[],
                confidence="none",
                mode="extractive",
            )

        keywords = {
            word
            for word in re.findall(r"[a-z]{4,}", question.lower())
            if word not in _STOPWORDS
        }

        scored: list[tuple[float, int, str]] = []
        for index, chunk in enumerate(contexts[:3], start=1):
            for sentence in re.split(r"(?<=[.!?])\s+", _strip_headings(chunk.text)):
                cleaned = " ".join(sentence.split())
                if len(cleaned) < 40:
                    continue
                tokens = set(re.findall(r"[a-z]{4,}", cleaned.lower()))
                overlap = len(keywords & tokens)
                if overlap:
                    scored.append((overlap / (len(keywords) or 1), index, cleaned))

        scored.sort(key=lambda item: item[0], reverse=True)
        selected = scored[:3]

        if not selected:
            # No sentence shared enough vocabulary with the question -- retrieval
            # matched on meaning rather than wording. Quote the passage verbatim
            # rather than assemble something the source does not say.
            excerpt = " ".join(_strip_headings(contexts[0].text).split())
            trimmed = excerpt[:400].rsplit(" ", 1)[0] if len(excerpt) > 400 else excerpt
            suffix = "..." if len(excerpt) > 400 else ""
            return GenerationResult(
                answered=True,
                answer=f"The most relevant policy passage states: {trimmed}{suffix} [1]",
                used_excerpts=[1],
                confidence="low",
                mode="extractive",
            )

        body = " ".join(
            f"{' '.join(sentence.split())} [{index}]" for _, index, sentence in selected
        )
        return GenerationResult(
            answered=True,
            answer=body,
            used_excerpts=sorted({index for _, index, _ in selected}),
            confidence="medium" if len(selected) > 1 else "low",
            mode="extractive",
        )


_STOPWORDS = {
    "what", "when", "where", "which", "does", "have", "with", "from", "this", "that",
    "your", "will", "there", "about", "would", "should", "could", "many", "much",
    "into", "they", "them", "then", "than", "only", "some", "must", "need", "just",
}

_HEADING_LINE = re.compile(
    r"^\s*(?:#{1,6}\s+.*|\d+(?:\.\d+)*[.)]?\s+[A-Z][^.!?]{0,80}|[A-Z][A-Z0-9 &/,'()\-]{4,70})\s*$"
)


def _strip_headings(text: str) -> str:
    """Drop heading-only lines so extracted sentences read as prose.

    Headings are kept in the indexed chunk because they carry retrieval signal,
    but quoting them back inside an answer looks like leaked markup.
    """
    kept = [line for line in text.split("\n") if not _HEADING_LINE.match(line)]
    return "\n".join(kept).strip() or text


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json_object(raw: str) -> dict | None:
    """Recover a JSON object from a model response that may be fenced or padded."""
    if not raw:
        return None

    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    match = _JSON_BLOCK.search(text)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _coerce_indices(value: object, maximum: int) -> list[int]:
    if not isinstance(value, list):
        return []
    indices: list[int] = []
    for item in value:
        try:
            index = int(item)
        except (TypeError, ValueError):
            continue
        if 1 <= index <= maximum and index not in indices:
            indices.append(index)
    return sorted(indices)


def _markers_in_text(text: str, maximum: int) -> list[int]:
    found: list[int] = []
    for raw in re.findall(r"\[(\d{1,2})\]", text):
        index = int(raw)
        if 1 <= index <= maximum and index not in found:
            found.append(index)
    return sorted(found)
