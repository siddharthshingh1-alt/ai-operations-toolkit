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
