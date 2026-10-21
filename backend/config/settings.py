"""
config/settings.py
Pydantic BaseSettings for the Trade Name Intelligence Service.

Covers:
  - Database, Redis, vLLM, TEI connection URLs
  - Per-capability feature flags: Off / Shadow / On  (F16, spec §5.3)
  - LLM gateway parameters: timeout, retry, circuit breaker  (spec §6.2)
  - Confidence thresholds for the decision policy  (spec §4.1)
  - Cache TTL  (spec §6.2)
  - JWT configuration  (spec §3.1 Auth)
  - Observability endpoints
"""
from enum import Enum
from functools import lru_cache
from typing import Optional, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class FlagMode(str, Enum):
    """
    Each AI capability flag accepts exactly three values (spec §5.3):
      off    – the capability is completely disabled; no LLM call is made.
      shadow – the capability runs and its result is logged, but it has
               no effect on the outcome returned to the caller.
      on     – the capability is live and its result affects outcomes.
    """
    off = "off"
    shadow = "shadow"
    on = "on"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env", "../backend/.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------
    # Service identity
    # ------------------------------------------------------------------
    service_name: str = Field(default="trade-name-intelligence-service")
    environment: str = Field(default="development")
    debug: bool = Field(default=False)

    # ------------------------------------------------------------------
    # Database  (spec §3.1 — SQLAlchemy 2.0 async + asyncpg)
    # ------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://tnis:tnis@localhost:5432/tnis",
        description="Async PostgreSQL DSN including +asyncpg driver",
    )
    db_pool_size: int = Field(default=20)
    db_max_overflow: int = Field(default=10)

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: Any) -> Any:
        if isinstance(v, str):
            if v.startswith("postgresql://"):
                v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
            v = v.replace("sslmode=require", "ssl=require")
            v = v.replace("&channel_binding=require", "").replace("?channel_binding=require", "")
        return v

    # ------------------------------------------------------------------
    # Redis  (spec §3.1 — arq workers + response cache)
    # ------------------------------------------------------------------
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis DSN for arq and response cache",
    )

    # ------------------------------------------------------------------
    # Dynamic LLM Provider & Gateway (Groq / OpenAI / Ollama / vLLM)
    # ------------------------------------------------------------------
    llm_provider: str = Field(
        default="groq",
        description="Active LLM provider: groq | openai | ollama | vllm",
    )
    llm_api_key: Optional[str] = Field(
        default=None,
        description="Generic fallback API Key for LLM provider",
    )
    groq_api_key: Optional[str] = Field(
        default=None,
        description="Persistent Groq API Key (gsk_...)",
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        description="Persistent OpenAI API Key (sk-...)",
    )
    llm_base_url: Optional[str] = Field(
        default=None,
        description="Explicit base URL (e.g. https://api.groq.com/openai/v1 or http://localhost:11434/v1)",
    )
    llm_analyzer_model: Optional[str] = Field(
        default=None,
        description="Model ID for Stage 4 analyzer (e.g. qwen-2.5-32b, qwen2.5:7b, gpt-4o-mini)",
    )
    llm_suggestions_model: Optional[str] = Field(
        default=None,
        description="Model ID for Stage 6 suggestions (e.g. qwen-2.5-32b, qwen2.5:7b, gpt-4o-mini)",
    )

    # vLLM — self-hosted OpenAI-compatible endpoint (spec §3.1, §6.2)
    vllm_base_url: str = Field(
        default="http://vllm:8080/v1",
        description="Base URL of the self-hosted vLLM endpoint (OpenAI-compatible)",
    )
    vllm_analyzer_model: str = Field(default="ded-analyzer-model")
    vllm_suggestions_model: str = Field(default="ded-suggestions-model")

    @property
    def effective_api_key(self) -> Optional[str]:
        provider = (self.llm_provider or "").lower().strip()
        if provider == "groq":
            if self.groq_api_key and self.groq_api_key.strip():
                return self.groq_api_key.strip()
            if self.llm_api_key and self.llm_api_key.strip():
                return self.llm_api_key.strip()
        if provider == "openai":
            if self.openai_api_key and self.openai_api_key.strip():
                return self.openai_api_key.strip()
            if self.llm_api_key and self.llm_api_key.strip():
                return self.llm_api_key.strip()
        if self.llm_api_key and self.llm_api_key.strip():
            return self.llm_api_key.strip()
        return None

    @property
    def effective_llm_base_url(self) -> str:
        if self.llm_base_url and self.llm_base_url.strip():
            return self.llm_base_url.rstrip("/")
        provider = (self.llm_provider or "").lower().strip()
        if provider == "groq":
            return "https://api.groq.com/openai/v1"
        if provider == "openai":
            return "https://api.openai.com/v1"
        if provider == "ollama":
            return "http://localhost:11434/v1"
        return self.vllm_base_url.rstrip("/")

    @property
    def effective_analyzer_model(self) -> str:
        if self.llm_analyzer_model and self.llm_analyzer_model.strip():
            return self.llm_analyzer_model.strip()
        provider = (self.llm_provider or "").lower().strip()
        if provider == "groq":
            return "qwen/qwen3.8-27b"
        if provider == "openai":
            return "gpt-4o-mini"
        if provider == "ollama":
            return "qwen2.5:7b"
        return self.vllm_analyzer_model

    @property
    def effective_suggestions_model(self) -> str:
        if self.llm_suggestions_model and self.llm_suggestions_model.strip():
            return self.llm_suggestions_model.strip()
        provider = (self.llm_provider or "").lower().strip()
        if provider == "groq":
            return "qwen/qwen3.8-27b"
        if provider == "openai":
            return "gpt-4o-mini"
        if provider == "ollama":
            return "qwen2.5:7b"
        return self.vllm_suggestions_model

    # ------------------------------------------------------------------
    # Text Embeddings Inference — multilingual embedding model  (spec §3.1)
    # ------------------------------------------------------------------
    tei_base_url: str = Field(
        default="http://tei:8081",
        description="Base URL of the self-hosted Text Embeddings Inference server",
    )
    # Embedding vector dimension — MUST match the deployed model output (Ambiguity #1)
    # Placeholder: 768 (e.g. intfloat/multilingual-e5-base). Update before first migration.
    embedding_dimension: int = Field(default=768)

    # ------------------------------------------------------------------
    # LLM Gateway parameters  (spec §6.2)
    # ------------------------------------------------------------------
    # 2.5 s timeout on the validation path
    llm_timeout_seconds: float = Field(default=2.5)
    # One retry on transient errors (5xx / network timeout); no retry on schema failures
    llm_max_retries: int = Field(default=1)
    # Circuit breaker: open after this many consecutive failures
    llm_circuit_breaker_threshold: int = Field(default=5)
    # Seconds before circuit moves from open → half-open
    llm_circuit_breaker_cooldown: int = Field(default=30)
    # Response cache TTL in seconds — 24 h per spec §6.2
    llm_cache_ttl_seconds: int = Field(default=86400)

    # ------------------------------------------------------------------
    # Decision policy thresholds  (spec §4.1 — tuned during shadow mode)
    # ------------------------------------------------------------------
    # LLM risk confidence at or above this → BLOCKED (when severity=block)
    policy_block_confidence_threshold: float = Field(default=0.85)
    # LLM risk confidence below this → NEEDS_REVIEW (when severity=block)
    policy_review_confidence_threshold: float = Field(default=0.60)
    # Deterministic name similarity rules shared by validation and registration.
    trade_name_similarity_review_threshold: float = Field(default=0.82, ge=0.0, le=1.0)
    trade_name_base_similarity_threshold: int = Field(default=88, ge=0, le=100)
    trade_name_base_min_confidence: float = Field(default=0.70, ge=0.0, le=1.0)
    # Optional additional descriptor vocabulary, comma-separated. Official
    # catalogue terms are always included by the extractor.
    trade_name_descriptors_en: str = Field(default="")
    trade_name_descriptors_ar: str = Field(default="")

    # ------------------------------------------------------------------
    # Per-capability feature flags  (F16, spec §5.3)
    # ------------------------------------------------------------------
    # Controls Stage ④ LLM semantic validation
    ai_analyzer: FlagMode = Field(default=FlagMode.off)
    # Controls Stage ⑥ LLM suggestion generation
    ai_suggestions: FlagMode = Field(default=FlagMode.on)
    # Controls Stage ⑧ Reviewer copilot
    ai_reviewer_brief: FlagMode = Field(default=FlagMode.off)
    # Controls Stage ③ hybrid semantic search (embedding component)
    ai_search: FlagMode = Field(default=FlagMode.off)
    # Controls Stage ⑨ LLM lexicon variant proposals
    ai_lexicon_proposals: FlagMode = Field(default=FlagMode.off)

    # ------------------------------------------------------------------
    # JWT / Auth  (spec §3.1 — validates JWTs from current identity provider)
    # Ambiguity #4: algorithm and JWKS URL TBD; using configurable placeholders
    # ------------------------------------------------------------------
    jwt_algorithm: str = Field(default="RS256")
    jwt_public_key: str = Field(
        default="",
        description="PEM-encoded public key for JWT verification (RS256). "
                    "Alternatively set jwt_jwks_url for dynamic key fetching.",
    )
    jwt_jwks_url: str = Field(
        default="",
        description="JWKS endpoint of the current identity provider. "
                    "Used if jwt_public_key is empty.",
    )
    # The JWT claim name that carries the channel value ("online" or "walkin")
    # Ambiguity #4: exact claim name to be confirmed with identity provider
    jwt_channel_claim: str = Field(default="channel")
    jwt_audience: str = Field(default="")
    jwt_issuer: str = Field(default="")

    # ------------------------------------------------------------------
    # Lexicon edit-distance threshold for variant matching  (spec §4.3)
    # ------------------------------------------------------------------
    lexicon_fuzzy_threshold: float = Field(
        default=90.0,
        description="RapidFuzz ratio threshold (0-100) for lexicon variant matching",
    )

    # ------------------------------------------------------------------
    # Observability  (spec §3.1)
    # ------------------------------------------------------------------
    otlp_endpoint: str = Field(default="http://otel-collector:4317")
    prometheus_port: int = Field(default=9090)
    log_level: str = Field(default="INFO")

    # ------------------------------------------------------------------
    # API server
    # ------------------------------------------------------------------
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)


_runtime_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Return the active settings instance (singleton or runtime updated)."""
    global _runtime_settings
    if _runtime_settings is None:
        _runtime_settings = Settings()
    return _runtime_settings


def reload_settings(new_settings: Optional[Settings] = None) -> Settings:
    """Update active settings instance at runtime."""
    global _runtime_settings
    if new_settings is not None:
        _runtime_settings = new_settings
    else:
        _runtime_settings = Settings()
    return _runtime_settings
