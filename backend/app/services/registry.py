"""File-backed metadata registry.

The vector store owns embeddings and chunk text; this registry owns everything
relational about a document (lifecycle status, ownership, versioning) plus the
query log. It is deliberately a single JSON file written atomically under a
lock -- the dataset for an internal policy base is small, and this keeps the
deployment to one process with no database to operate.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_EMPTY_STATE: dict[str, Any] = {"schema_version": 1, "documents": {}, "queries": []}
_MAX_QUERIES = 2000


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialise(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Unserialisable type: {type(value).__name__}")


class MetadataRegistry:
    """Small, process-local document store with atomic writes."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._state = self._load()

    # -- persistence ------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return json.loads(json.dumps(_EMPTY_STATE))
        try:
            with self._path.open("r", encoding="utf-8") as handle:
                state = json.load(handle)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("registry_load_failed path=%s error=%s", self._path, exc)
            backup = self._path.with_suffix(".corrupt.json")
            try:
                self._path.replace(backup)
                logger.error("registry_quarantined backup=%s", backup)
            except OSError:
                pass
            return json.loads(json.dumps(_EMPTY_STATE))

        state.setdefault("documents", {})
        state.setdefault("queries", [])
        state.setdefault("schema_version", 1)
        return state

    def _flush(self) -> None:
        """Write via a temp file + replace so a crash cannot truncate state."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(self._path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self._state, handle, indent=2, default=_serialise)
            os.replace(tmp_name, self._path)
        except Exception:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
            raise

    # -- documents --------------------------------------------------------

    def upsert_document(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            record = dict(record)
            record["updated_at"] = utcnow().isoformat()
            self._state["documents"][record["id"]] = record
            self._flush()
            return record

    def patch_document(self, document_id: str, **fields: Any) -> dict[str, Any] | None:
        with self._lock:
            record = self._state["documents"].get(document_id)
            if record is None:
                return None
            record.update(fields)
            record["updated_at"] = utcnow().isoformat()
            self._flush()
            return record

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._state["documents"].get(document_id)
            return dict(record) if record else None

    def delete_document(self, document_id: str) -> bool:
        with self._lock:
            removed = self._state["documents"].pop(document_id, None)
            if removed is None:
                return False
            self._flush()
            return True

    def list_documents(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            records = [dict(item) for item in self._state["documents"].values()]

        if status:
            records = [r for r in records if r.get("status") == status]
        if category:
            records = [r for r in records if r.get("category") == category]
        if search:
            needle = search.lower().strip()
            records = [
                r
                for r in records
                if needle in str(r.get("title", "")).lower()
                or needle in str(r.get("owner", "")).lower()
                or needle in str(r.get("filename", "")).lower()
            ]

        records.sort(key=lambda r: r.get("uploaded_at", ""), reverse=True)
        return records

    def published_document_ids(self) -> set[str]:
        with self._lock:
            return {
                doc_id
                for doc_id, record in self._state["documents"].items()
                if record.get("status") == "published"
            }

    # -- query log --------------------------------------------------------

    def append_query(self, entry: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._state["queries"].append(entry)
            if len(self._state["queries"]) > _MAX_QUERIES:
                self._state["queries"] = self._state["queries"][-_MAX_QUERIES:]
            self._flush()
            return entry

    def set_query_feedback(
        self, query_id: str, rating: str, comment: str | None
    ) -> dict[str, Any] | None:
        with self._lock:
            for entry in reversed(self._state["queries"]):
                if entry.get("id") == query_id:
                    entry["feedback"] = rating
                    entry["feedback_comment"] = comment
                    entry["feedback_at"] = utcnow().isoformat()
                    self._flush()
                    return dict(entry)
            return None

    def list_queries(self, limit: int = 50, offset: int = 0) -> tuple[list[dict[str, Any]], int]:
        with self._lock:
            queries = list(reversed(self._state["queries"]))
        return [dict(q) for q in queries[offset : offset + limit]], len(queries)

    def all_queries(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(q) for q in self._state["queries"]]

    def stats(self) -> dict[str, int]:
        with self._lock:
            documents = self._state["documents"].values()
            return {
                "documents_total": len(self._state["documents"]),
                "documents_published": sum(1 for d in documents if d.get("status") == "published"),
                "documents_archived": sum(1 for d in documents if d.get("status") == "archived"),
                "queries_total": len(self._state["queries"]),
            }
