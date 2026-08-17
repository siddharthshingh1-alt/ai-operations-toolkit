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


# ------------------------------------------------- the remote-schema refusal
#
# Added after `create_all()` twice issued CREATE TABLE against the deployed
# database from a developer's laptop: `.env` had DATABASE_URL pointing at
# production with DB_AUTO_CREATE left on, so merely importing the app was
# enough. Configuration could not fix that — `.env` was the thing that was
# wrong — so the refusal lives at the call site instead.


def _db_settings(url: str | None, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "database_url": url,
        "demo_mode": True,
        "anthropic_api_key": None,
        "openai_api_key": None,
        "google_api_key": None,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "url",
    [
        None,
        "sqlite://",
        "sqlite:///./local.db",
        "postgresql://aiops:aiops@localhost:5432/aiops",
        "postgresql://aiops:aiops@127.0.0.1:5432/aiops",
        # The hostname docker-compose gives the database service.
        "postgresql://aiops:aiops@db:5432/aiops",
    ],
)
def test_a_local_database_is_recognised(url: str | None) -> None:
    from aiops_db.schema import is_local_database

    assert is_local_database(_db_settings(url)) is True


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://user:pw@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres",
        "postgresql://user:pw@db.abcdefgh.supabase.co:5432/postgres",
        "postgresql://user:pw@some-host.neon.tech/main",
        "postgresql://user:pw@10.0.0.5:5432/prod",
    ],
)
def test_a_remote_database_is_not_local(url: str) -> None:
    from aiops_db.schema import is_local_database

    assert is_local_database(_db_settings(url)) is False


def test_create_all_refuses_a_remote_database() -> None:
    """The exact accident, prevented. No connection is attempted."""
    from aiops_db.schema import create_all
    from aiops_utils import RemoteSchemaRefused

    settings = _db_settings("postgresql://user:pw@aws-0-ap-south-1.pooler.supabase.com:5432/db")
    with pytest.raises(RemoteSchemaRefused) as caught:
        create_all(settings)

    message = str(caught.value)
    assert "local" in message.lower()
    # The message is logged, and the URL it came from contains a password, so
    # the host must not be echoed into it.
    assert "supabase" not in message.lower()
    assert "pw" not in message.split()


def test_the_refusal_can_be_overridden_deliberately() -> None:
    """A real migration against a remote database must remain possible.

    The override is checked here rather than the creation being performed —
    that would need a live remote database. What matters is that the refusal
    is keyed on the flag, so setting it is what changes the outcome.
    """
    from aiops_db.schema import create_all
    from aiops_utils import RemoteSchemaRefused

    settings = _db_settings(
        "postgresql://user:pw@aws-0-ap-south-1.pooler.supabase.com:5432/db",
        db_allow_remote_schema=True,
    )
    # It gets past the guard, then fails trying to reach a host that does not
    # exist — which is proof the refusal is no longer what stopped it.
    with pytest.raises(Exception) as caught:  # noqa: B017 — any connection error will do
        create_all(settings)
    assert not isinstance(caught.value, RemoteSchemaRefused)


def test_the_override_is_off_by_default() -> None:
    assert _db_settings(None).db_allow_remote_schema is False
