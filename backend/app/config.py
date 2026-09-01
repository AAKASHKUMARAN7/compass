"""Application configuration.

All runtime behaviour is driven from environment variables so the same build can
be promoted across environments without code changes.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

LLMProvider = Literal["google", "openai", "none"]
EmbeddingProvider = Literal["google", "openai", "local"]


class Settings(BaseSettings):
    """Typed application settings resolved once at process start."""

    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -- Service identity -------------------------------------------------
    app_name: str = "Compass Policy Intelligence API"
    app_version: str = "1.0.0"
    environment: Literal["local", "staging", "production"] = "local"
    log_level: str = "INFO"

    # -- Transport --------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8010
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # -- Model providers --------------------------------------------------
    google_api_key: str | None = None
    openai_api_key: str | None = None

    llm_provider: LLMProvider = "google"
    embedding_provider: EmbeddingProvider = "google"

    google_chat_model: str = "gemini-3.1-flash-lite"
    google_embedding_model: str = "models/text-embedding-004"
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    llm_temperature: float = 0.1
    llm_timeout_seconds: int = 45
    # Headroom for models that reason internally, since those tokens count
    # against this budget. Measured on gemini-3.5-flash: 170 output tokens but
    # ~690 of thinking, which intermittently truncated the JSON reply at 1024
    # and surfaced as a silent drop to the extractive fallback. The default
    # model is a lite variant that does not think, but the headroom keeps a
    # heavier model swappable without re-tuning.
    llm_max_output_tokens: int = 4096

    # -- Retrieval tuning -------------------------------------------------
    chunk_size: int = 1100
    chunk_overlap: int = 160
    retrieval_top_k: int = 6
    # Weight of the lexical arm when fusing with dense similarity. Applied as a
    # maximum against the raw vector score, so it can only rescue a chunk that
    # dense retrieval under-ranked -- never demote one it ranked well.
    lexical_weight: float = 0.45
    # Cosine-similarity floor. Below this the assistant refuses to answer and
    # the question is recorded as a knowledge-base coverage gap.
    #
    # Calibrated against the active embedding model by scoring known in-policy
    # and out-of-policy questions: with all-MiniLM-L6-v2 true matches land in
    # 0.55-0.81 and off-topic questions in 0.16-0.43, so the gate sits in the
    # gap between the two populations. Re-measure when changing the embedding
    # model -- the absolute scale differs per model.
    min_relevance_score: float = 0.48
    high_confidence_score: float = 0.66

    # -- Storage ----------------------------------------------------------
    data_dir: Path = BASE_DIR / "data"
    chroma_collection: str = "policy_chunks"
    max_upload_bytes: int = 15 * 1024 * 1024

    @field_validator("cors_origins")
    @classmethod
    def _strip_origins(cls, value: str) -> str:
        return value.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def registry_path(self) -> Path:
        return self.data_dir / "registry.json"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def active_llm_key(self) -> str | None:
        if self.llm_provider == "google":
            return self.google_api_key
        if self.llm_provider == "openai":
            return self.openai_api_key
        return None

    @property
    def llm_enabled(self) -> bool:
        return bool(self.active_llm_key)

    def ensure_directories(self) -> None:
        for path in (self.data_dir, self.chroma_dir, self.uploads_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
