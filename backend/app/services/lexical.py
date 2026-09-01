"""Lexical retrieval and query normalisation.

Dense embeddings are strong on paraphrase and weak on morphology and rare
terms. Measured against this corpus, `all-MiniLM-L6-v2` scores "annual leave"
at 0.70 but "annual leaves" at 0.23 -- the plural collides with the verb and
foliage senses, and "leaves" is how most employees actually phrase it.

Two complementary defences live here:

* `singularise` folds plural nouns so the query can also be embedded in a form
  the model handles well. The better of the two similarities wins, so
  normalisation can only help.
* `LexicalIndex` scores how much of the question's vocabulary literally appears
  in a chunk, IDF-weighted, over a lightly stemmed index. It is bounded to
  [0, 1] like cosine similarity so both signals share one calibrated floor.
"""

from __future__ import annotations

import math
import re
import threading
from dataclasses import dataclass, field
from typing import Iterable

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Terms that carry no retrieval signal in a policy corpus.
_STOPWORDS = frozenset(
    """
    a an the and or but if then than that this these those there here
    is are was were be been being am do does did doing done have has had having
    i me my we us our you your he she it its they them their
    what when where which who whom whose why how
    of in on at to for from by with without within into onto up down out off over under
    can could shall should will would may might must need
    as so such not no nor only just also very more most much many any all both each
    about after before between during through
    get got give gives take takes list show tell know
    """.split()
)

# Words whose plural form is the natural or only form in this domain.
_KEEP_PLURAL = frozenset(
    {
        "business",
        "expenses",
        "premises",
        "hours",
        "process",
        "access",
        "address",
        "witness",
        "class",
    }
)

_WORD_RE = re.compile(r"\b[a-z]{4,}\b")


def singularise(text: str) -> str:
    """Fold plural nouns to singular while preserving sentence structure.

    Rules are applied to the whole word rather than to regex groups, because a
    greedy group would split "policies" as "policie" + "s" and never reach the
    "ies" rule.

    Deliberately conservative: this produces an *additional* query variant and
    never replaces the original, so an over-eager fold costs nothing beyond one
    extra embedding.
    """

    def replace(match: re.Match[str]) -> str:
        word = match.group(0)

        if word in _KEEP_PLURAL or word in _STOPWORDS or not word.endswith("s"):
            return word
        # "business", "status", "analysis" -- not plurals.
        if word.endswith(("ss", "us", "is")):
            return word
        if len(word) > 4 and word.endswith("ies"):
            return word[:-3] + "y"
        if word.endswith(("sses", "shes", "ches", "xes", "zes")):
            return word[:-2]
        return word[:-1]

    return _WORD_RE.sub(replace, text.lower())


def query_variants(query: str) -> list[str]:
    """The query plus any normalised form worth embedding separately."""
    variants = [query]
    folded = singularise(query)
    if folded and folded != query.lower():
        variants.append(folded)
    return variants


def stem(token: str) -> str:
    """Very small suffix stripper for the lexical index.

    Not linguistically complete -- it only needs to collapse the inflections
    that appear in policy questions: plurals, gerunds and past tense. A full
    stemmer would be a dependency and a behaviour change for marginal gain.
    """
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith(("sses", "shes", "ches", "xes")):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        token = token[:-1]
    if len(token) > 5 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 4 and token.endswith("ed"):
        return token[:-2]
    return token


def tokenise(text: str) -> list[str]:
    return [
        stem(token)
        for token in _TOKEN_RE.findall(text.lower())
        if len(token) > 1 and token not in _STOPWORDS
    ]


@dataclass
class LexicalEntry:
    chunk_id: str
    document_id: str
    terms: frozenset[str] = field(default_factory=frozenset)


class LexicalIndex:
    """In-memory term index over the indexed chunks.

    The corpus is small (hundreds of chunks for a policy base), so an inverted
    index with recomputed IDF on write is cheaper and simpler than maintaining
    a second persistent store. It is rebuilt from the vector store at startup.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: dict[str, LexicalEntry] = {}
        self._document_frequency: dict[str, int] = {}

    # -- writes -----------------------------------------------------------

    def add(self, chunk_id: str, document_id: str, text: str) -> None:
        terms = frozenset(tokenise(text))
        with self._lock:
            existing = self._entries.get(chunk_id)
            if existing is not None:
                self._decrement(existing.terms)
            self._entries[chunk_id] = LexicalEntry(chunk_id, document_id, terms)
            for term in terms:
                self._document_frequency[term] = self._document_frequency.get(term, 0) + 1

    def remove_document(self, document_id: str) -> None:
        with self._lock:
            doomed = [
                entry for entry in self._entries.values() if entry.document_id == document_id
            ]
            for entry in doomed:
                self._decrement(entry.terms)
                self._entries.pop(entry.chunk_id, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._document_frequency.clear()

    def _decrement(self, terms: Iterable[str]) -> None:
        for term in terms:
            remaining = self._document_frequency.get(term, 0) - 1
            if remaining > 0:
                self._document_frequency[term] = remaining
            else:
                self._document_frequency.pop(term, None)

    # -- reads ------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._entries)

    def vocabulary_size(self) -> int:
        with self._lock:
            return len(self._document_frequency)

    def coverage(self, query: str) -> dict[str, float]:
        """Score chunks by the share of the question's vocabulary they contain.

        Terms are IDF-weighted and every query term counts toward the
        denominator, including terms the corpus has never seen. That is
        deliberate: an unseen term is evidence the topic is not covered, and
        dropping such terms was measured to let "sabbatical after five years of
        service" score 0.63 purely on the incidental words "years" and
        "service".

        The cost is that generic unseen words ("total", "available") also drag
        the score down, so this arm alone cannot rescue a terse query. Query
        normalisation in `singularise` handles that case at the source instead.
        """
        query_terms = set(tokenise(query))
        if not query_terms:
            return {}

        with self._lock:
            total_documents = len(self._entries)
            if total_documents == 0:
                return {}

            weights = {
                term: math.log(
                    1.0 + total_documents / (1 + self._document_frequency.get(term, 0))
                )
                for term in query_terms
            }
            total_weight = sum(weights.values())
            if total_weight <= 0:
                return {}

            scores: dict[str, float] = {}
            for entry in self._entries.values():
                matched = query_terms & entry.terms
                if not matched:
                    continue
                scores[entry.chunk_id] = sum(weights[term] for term in matched) / total_weight
            return scores

    def unknown_ratio(self, query: str) -> float:
        """Fraction of the question's content terms absent from the corpus."""
        query_terms = set(tokenise(query))
        if not query_terms:
            return 0.0
        with self._lock:
            unknown = sum(
                1 for term in query_terms if self._document_frequency.get(term, 0) == 0
            )
        return unknown / len(query_terms)

    def top_chunk_ids(
        self,
        query: str,
        *,
        limit: int,
        allowed_document_ids: set[str] | None = None,
    ) -> list[tuple[str, float]]:
        scores = self.coverage(query)
        if allowed_document_ids is not None:
            scores = {
                chunk_id: score
                for chunk_id, score in scores.items()
                if self._entries[chunk_id].document_id in allowed_document_ids
            }
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        return ranked[:limit]
