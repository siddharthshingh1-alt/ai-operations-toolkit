"""Global exception handling.

CLAUDE.md Section 23: clear error messages, and never a raw stack trace shown
to a normal user. Technical detail goes to the log; the response carries only
the safe `user_message`.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from aiops_utils import AIOpsError, get_logger

logger = get_logger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    """Attach the handlers to the application."""

    @app.exception_handler(AIOpsError)
    async def handle_known_error(request: Request, exc: AIOpsError) -> JSONResponse:
        """Errors we raised deliberately, with a user-safe message attached."""
        logger.warning(
            "handled application error",
            extra={
                "code": exc.code,
                "detail": exc.detail,
                "path": request.url.path,
            },
        )
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Bad request shape. FastAPI's default body is developer-facing."""
        logger.info(
            "request validation failed",
            extra={"path": request.url.path, "errors": exc.errors()},
        )
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_error",
                "message": "Some of the information sent was not valid.",
                # Field-level detail is safe and genuinely useful to a client.
                "fields": [
                    {"field": ".".join(str(p) for p in err["loc"][1:]), "problem": err["msg"]}
                    for err in exc.errors()
                ],
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        """Anything we did not anticipate. The traceback goes to the log only."""
        logger.exception("unhandled error", extra={"path": request.url.path})
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "message": "Something went wrong on our side. Please try again.",
            },
        )
