"""Validated application settings, loaded from the environment.

Usage:

    from aiops_config import get_settings

    settings = get_settings()
    if settings.demo_mode:
        ...

`get_settings()` is cached, so the `.env` file is read once per process.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from aiops_config.paths import repo_root


class ProviderName(StrEnum):
    """AI providers supported by the shared AI layer (CLAUDE.md Section 3)."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"


class AuthMode(StrEnum):
    """Authentication modes. v1 ships `DEMO` so reviewers never hit a login wall."""

    DEMO = "demo"
    SUPABASE = "supabase"


class Settings(BaseSettings):
    """All runtime configuration for the toolkit.

    Field names map to the upper-case variables documented in `.env.example`.
    """

    model_config = SettingsConfigDict(
        env_file=str(repo_root() / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ----- app -----------------------------------------------------------
    app_env: str = "development"
    app_name: str = "AI Operations Toolkit"
    log_level: str = "INFO"

    # ----- demo mode (Section 3b) ----------------------------------------
    demo_mode: bool = True
    allow_bring_your_own_key: bool = True

    # ----- AI provider (Section 3) ---------------------------------------
    ai_provider: ProviderName = ProviderName.ANTHROPIC
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    google_api_key: str | None = None
    gemini_model: str = "gemini-3.6-flash"

    # Tried in order when `gemini_model` reports its quota spent (Section 3b).
    #
    # This helps when the free tier meters *per model*, which it commonly does:
    # the next model has its own allowance, so the day's budget is larger than
    # any one model's. It does nothing when the cap is project-wide — there is
    # no way to tell the two apart from the error, so the fallback is offered
    # as an attempt and never described to a visitor as a guarantee.
    #
    # Set to an empty list to disable and fail on the first quota error.
    gemini_fallback_models: list[str] = Field(
        default_factory=lambda: ["gemini-3.5-flash", "gemini-3.5-flash-lite"]
    )

    # Anthropic offers neither embeddings nor speech-to-text, so these two
    # capabilities are configured separately from the main chat provider.
    embedding_provider: ProviderName = ProviderName.OPENAI
    openai_embedding_model: str = "text-embedding-3-small"
    gemini_embedding_model: str = "gemini-embedding-001"

    # Gemini's embedding models return 3072 dimensions by default, but
    # pgvector cannot build an HNSW or IVFFlat index above 2000. The model
    # supports Matryoshka truncation, so we ask for a smaller vector that is
    # both indexable and cheaper to store.
    #
    # Changing this after SOPs have been embedded requires re-embedding them —
    # the database column has a fixed width.
    gemini_embedding_dimensions: int = Field(default=1536, gt=0, le=2000)

    transcribe_provider: ProviderName = ProviderName.OPENAI
    openai_transcribe_model: str = "whisper-1"

    ai_max_output_tokens: int = Field(default=24576, gt=0)
    ai_timeout_seconds: float = Field(default=90.0, gt=0)
    ai_max_retries: int = Field(default=2, ge=0, le=5)

    # ----- database ------------------------------------------------------
    database_url: str | None = None
    db_auto_create: bool = False

    # ----- auth (Section 3) ----------------------------------------------
    auth_mode: AuthMode = AuthMode.DEMO
    demo_user_email: str = "demo@aiops.local"
    demo_user_name: str = "Demo Operator"

    # ----- integrations (Section 3c — mock only in v1) --------------------
    email_provider: str = "mock"
    calendar_provider: str = "mock"
    booking_provider: str = "mock"

    # ----- storage -------------------------------------------------------
    storage_provider: str = "local"
    storage_local_path: str = "./storage"
    max_upload_mb: int = Field(default=20, gt=0)

    # ----- frontend / CORS -----------------------------------------------
    next_public_api_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:3000"

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = value.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}, got {value!r}")
        return upper

    @field_validator("database_url")
    @classmethod
    def _normalise_database_driver(cls, value: str | None) -> str | None:
        """Name the psycopg driver explicitly in the connection URL.

        Managed Postgres providers (Supabase, Neon, Railway) hand out URLs
        starting `postgresql://` or the legacy `postgres://`. SQLAlchemy reads
        the bare form as "use psycopg2", which is not installed — the failure is
        an unhelpful ModuleNotFoundError at first connection.

        Rewriting it here means the connection string can be pasted exactly as
        the provider gives it, with no hand-editing to get wrong.
        """
        if not value or not value.strip():
            return value

        url = value.strip()
        for prefix in ("postgresql+psycopg://", "postgresql+psycopg2://"):
            if url.startswith(prefix):
                return url  # already explicit — leave the author's choice alone

        for legacy in ("postgresql://", "postgres://"):
            if url.startswith(legacy):
                return "postgresql+psycopg://" + url[len(legacy) :]

        return url

    @field_validator("email_provider", "calendar_provider", "booking_provider")
    @classmethod
    def _mock_only_in_v1(cls, value: str) -> str:
        """v1 is mock-only by decision (CLAUDE.md Section 3c).

        Real OAuth integrations are a documented future improvement. Failing
        loudly here prevents a half-built OAuth flow from being switched on by
        accident.
        """
        if value != "mock":
            raise ValueError(
                f"{value!r} is not available in v1. Integrations are mock-only "
                "(CLAUDE.md Section 3c); real OAuth is a future improvement."
            )
        return value

    # ----- derived helpers ------------------------------------------------
    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins as a list, parsed from the comma-separated setting."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def database_configured(self) -> bool:
        """True when a database connection string has been supplied."""
        return bool(self.database_url and self.database_url.strip())

    def api_key_for(self, provider: ProviderName) -> str | None:
        """Return the configured API key for `provider`, if any."""
        return {
            ProviderName.ANTHROPIC: self.anthropic_api_key,
            ProviderName.OPENAI: self.openai_api_key,
            ProviderName.GEMINI: self.google_api_key,
        }[provider]

    def model_for(self, provider: ProviderName) -> str:
        """Return the default model name for `provider`."""
        return {
            ProviderName.ANTHROPIC: self.anthropic_model,
            ProviderName.OPENAI: self.openai_model,
            ProviderName.GEMINI: self.gemini_model,
        }[provider]

    def redacted(self) -> dict[str, object]:
        """Settings safe to expose over HTTP — every secret removed.

        Used by the `/health` endpoint. Never serialise `Settings` directly.
        """
        return {
            "app_env": self.app_env,
            "app_name": self.app_name,
            "demo_mode": self.demo_mode,
            "allow_bring_your_own_key": self.allow_bring_your_own_key,
            "ai_provider": self.ai_provider.value,
            "auth_mode": self.auth_mode.value,
            "database_configured": self.database_configured,
            "email_provider": self.email_provider,
            "calendar_provider": self.calendar_provider,
            "booking_provider": self.booking_provider,
            "storage_provider": self.storage_provider,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()


def reset_settings_cache() -> None:
    """Clear the cached settings. Used by tests that patch the environment."""
    get_settings.cache_clear()
