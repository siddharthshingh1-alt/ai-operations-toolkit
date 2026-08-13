"""Configuration and secret-safety tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from aiops_config import ProviderName, Settings, repo_root


def test_repo_root_is_found() -> None:
    """Path resolution must work regardless of the current directory."""
    root = repo_root()
    assert (root / "requirements.txt").is_file()
    assert (root / "package.json").is_file()


def test_defaults_are_reviewer_friendly() -> None:
    """A reviewer with no .env should land in Demo Mode with no login wall."""
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.demo_mode is True
    assert settings.auth_mode.value == "demo"
    assert settings.database_configured is False


def test_redacted_never_contains_a_secret() -> None:
    """The /health payload must not be able to leak a key."""
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        anthropic_api_key="sk-ant-SECRET-VALUE",
        openai_api_key="sk-openai-SECRET-VALUE",
        database_url="postgresql+psycopg://user:PASSWORD@host/db",
    )
    serialised = str(settings.redacted())
    assert "SECRET-VALUE" not in serialised
    assert "PASSWORD" not in serialised
    # But it still reports that a database is configured.
    assert settings.redacted()["database_configured"] is True


def test_real_integrations_are_rejected_in_v1() -> None:
    """CLAUDE.md Section 3c: v1 is mock-only, enforced at config load."""
    with pytest.raises(PydanticValidationError, match="not available in v1"):
        Settings(_env_file=None, email_provider="gmail")  # type: ignore[call-arg]

    with pytest.raises(PydanticValidationError, match="not available in v1"):
        Settings(_env_file=None, calendar_provider="google")  # type: ignore[call-arg]


def test_invalid_log_level_is_rejected() -> None:
    with pytest.raises(PydanticValidationError, match="log_level must be one of"):
        Settings(_env_file=None, log_level="CHATTY")  # type: ignore[call-arg]


def test_cors_origins_parse_into_a_list() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        cors_origins="http://localhost:3000, https://example.test ,",
    )
    assert settings.cors_origin_list == ["http://localhost:3000", "https://example.test"]


def test_api_key_lookup_per_provider() -> None:
    settings = Settings(_env_file=None, anthropic_api_key="a", openai_api_key="b")  # type: ignore[call-arg]
    assert settings.api_key_for(ProviderName.ANTHROPIC) == "a"
    assert settings.api_key_for(ProviderName.OPENAI) == "b"
    assert settings.api_key_for(ProviderName.GEMINI) is None
