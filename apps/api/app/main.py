"""FastAPI application entry point.

Run it with:

    npm run dev:api

or directly:

    .venv/Scripts/python -m uvicorn app.main:app --reload   (from apps/api)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aiops_dashboard.router import router as dashboard_router
from aiops_sop.router import router as sop_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aiops_config import get_settings
from aiops_utils import configure_logging, get_logger
from app.errors import register_error_handlers
from app.routers import health

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start-up and shut-down."""
    settings = get_settings()
    configure_logging(settings.log_level)

    logger.info(
        "api starting",
        extra={
            "env": settings.app_env,
            "demo_mode": settings.demo_mode,
            "database_configured": settings.database_configured,
        },
    )

    # Optional convenience for local development only. Production uses Alembic.
    if settings.database_configured and settings.db_auto_create:
        from aiops_db import create_all

        create_all(settings)

    yield
    logger.info("api stopping")


def create_app() -> FastAPI:
    """Build the application. A factory keeps tests independent of import order."""
    settings = get_settings()

    app = FastAPI(
        title=f"{settings.app_name} API",
        description=(
            "Backend for the AI Operations Toolkit — AI-assisted workflows, SOPs, "
            "dashboards, trackers, and automations for B2B travel operations."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    app.include_router(health.router)

    # Each project mounts its own router here as it is built; the router
    # carries its own prefix.
    app.include_router(sop_router)  # Project 1 — AI SOP Generator
    app.include_router(dashboard_router)  # Project 3 — AI Operations Dashboard
    return app


app = create_app()
