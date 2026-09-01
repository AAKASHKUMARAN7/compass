"""Structured logging setup.

Emits single-line key=value records that are cheap to grep locally and trivial
to parse once shipped to a log aggregator.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Attaches the ambient request id to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


_FORMAT = "%(asctime)s level=%(levelname)s request_id=%(request_id)s logger=%(name)s msg=%(message)s"


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S"))
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Vector store and HTTP clients are chatty at INFO; keep the signal readable.
    for noisy in ("chromadb", "httpx", "httpcore", "urllib3", "google_genai", "pypdf"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
