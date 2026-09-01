"""Application entrypoint.

Run locally with:
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger, request_id_var
from app.dependencies import build_container

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)

DESCRIPTION = """
Compass indexes an organisation's policy documents and answers employee
questions strictly from that content, with inline citations back to the source
section.

Design notes:

* **Grounding gate** - retrieval below the configured relevance floor returns
  `status = no_coverage` instead of a speculative answer.
* **Server-bound citations** - the model selects excerpt numbers; document
  title, section, page and version are attached server-side from the index, so
  a source cannot be fabricated.
* **Coverage gaps** - refused questions are logged and surfaced as a
  prioritised content backlog for the policy owner.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Resolve providers and open the vector store once per process."""
    logger.info(
        "startup app=%s version=%s environment=%s",
        settings.app_name,
        settings.app_version,
        settings.environment,
    )
    app.state.container = build_container(settings)
    try:
        yield
    finally:
        logger.info("shutdown app=%s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    description=DESCRIPTION,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time-Ms"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Tag every request with an id and record its latency."""
    request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
    token = request_id_var.set(request_id)
    started = time.perf_counter()

    try:
        response = await call_next(request)
    finally:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        request_id_var.reset(token)

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = str(elapsed_ms)

    if request.url.path.startswith("/api"):
        logger.info(
            "request method=%s path=%s status=%d duration_ms=%d",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
    return response


register_exception_handlers(app)
app.include_router(api_router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "local",
    )
