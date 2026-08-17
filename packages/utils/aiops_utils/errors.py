"""Typed errors shared across the toolkit.

CLAUDE.md Section 23 requires clear error messages and forbids showing raw
stack traces to normal users. Every error here therefore carries a
`user_message` that is safe to display, separate from the technical detail that
goes to the logs.
"""

from __future__ import annotations


class AIOpsError(Exception):
    """Base class for every error the toolkit raises deliberately."""

    #: HTTP status the API layer should use when this error escapes.
    status_code: int = 500
    #: Short, stable, machine-readable code (e.g. for frontend branching).
    code: str = "internal_error"
    #: Default message shown to a non-technical user.
    default_user_message: str = "Something went wrong. Please try again."

    def __init__(self, detail: str, *, user_message: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.user_message = user_message or self.default_user_message

    def to_payload(self) -> dict[str, str]:
        """Safe JSON body for an API response — never includes a traceback."""
        return {"code": self.code, "message": self.user_message}


class ConfigurationError(AIOpsError):
    """A required setting is missing or invalid."""

    status_code = 500
    code = "configuration_error"
    default_user_message = "The server is not configured correctly. Please contact the operator."


class RemoteSchemaRefused(ConfigurationError):
    """Table creation was attempted against a database that is not local.

    A subclass of `ConfigurationError` because that is exactly what it is: the
    process is pointed somewhere its author did not intend. It is named
    separately so the local-development bootstrap can be caught and reported
    specifically, rather than being mistaken for a missing setting.
    """

    code = "remote_schema_refused"
    default_user_message = (
        "The server is not configured correctly: it tried to create database "
        "tables on a database that is not its own. Please contact the operator."
    )


class ValidationError(AIOpsError):
    """User-supplied input failed validation."""

    status_code = 422
    code = "validation_error"
    default_user_message = "The information provided is not valid. Please check and try again."


class NotFoundError(AIOpsError):
    """A requested resource does not exist."""

    status_code = 404
    code = "not_found"
    default_user_message = "That item could not be found."


class DatabaseUnavailable(AIOpsError):
    """The database could not be reached.

    Separate from `ConfigurationError` because nothing is misconfigured: the
    settings are fine and the database is simply not answering. Separate from a
    generic 500 because "something went wrong" tells an operator nothing and a
    visitor even less — and because the parts of this toolkit that need no
    database keep working, so the failure is partial rather than total.
    """

    status_code = 503
    code = "database_unavailable"
    default_user_message = (
        "The database is temporarily unavailable, so saved data cannot be read "
        "or written right now. Features that do not need it still work."
    )


class AIProviderError(AIOpsError):
    """The AI provider returned an error or an unusable response."""

    status_code = 502
    code = "ai_provider_error"
    default_user_message = (
        "The AI service could not complete this request. Your data was not changed."
    )


class AIProviderTimeout(AIProviderError):
    """The AI provider did not respond within the configured timeout."""

    status_code = 504
    code = "ai_provider_timeout"
    default_user_message = "The AI service took too long to respond. Please try again."


class AIQuotaExhausted(AIProviderError):
    """The provider's quota or rate limit is spent.

    Separated from `AIProviderError` because it is not a fault: the public demo
    runs live AI on a free tier deliberately, so reaching the daily limit is a
    documented, expected end state. Presenting it as "the AI service could not
    complete this request" would describe a healthy system as a broken one, and
    would leave a visitor with no idea whether waiting helps.
    """

    status_code = 429
    code = "ai_quota_exhausted"
    default_user_message = (
        "This demo runs on a free AI tier (about 20 requests a day). Today's "
        "limit has been reached — please try again tomorrow."
    )


def provider_http_error(detail: str, *, status_code: int | None) -> AIProviderError:
    """The right error for a failed provider HTTP call.

    Exists so every provider treats a 429 the same way. Gemini's SDK does not
    expose a status code reliably and is handled in that provider; the OpenAI
    and Anthropic SDKs both do, and both route through here.
    """
    if status_code == 429:
        return AIQuotaExhausted(detail)
    return AIProviderError(detail)
