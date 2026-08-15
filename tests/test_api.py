"""API tests: health endpoints and error handling."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aiops_utils import NotFoundError, ValidationError
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_liveness_is_always_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_reports_every_dependency(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] in {"ok", "degraded", "unhealthy"}
    names = {check["name"] for check in body["checks"]}
    assert names == {"database", "ai", "pdf_export"}


def test_missing_optional_dependency_is_degraded_not_unhealthy(
    client: TestClient,
) -> None:
    """Demo Mode with no database is working as designed, not broken."""
    body = client.get("/health/ready").json()
    database = next(c for c in body["checks"] if c["name"] == "database")

    if database["status"] == "not_configured":
        assert body["status"] == "degraded"


def test_system_info_exposes_no_secrets(client: TestClient) -> None:
    response = client.get("/api/system")
    assert response.status_code == 200

    body = response.json()
    assert "demo_mode" in body
    for forbidden in ("api_key", "anthropic_api_key", "database_url", "password"):
        assert forbidden not in body


def test_openapi_schema_is_generated(client: TestClient) -> None:
    """A broken route signature usually shows up here first."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/health" in response.json()["paths"]


def test_known_errors_return_a_safe_payload() -> None:
    """CLAUDE.md Section 23: no stack trace reaches the user."""
    app: FastAPI = create_app()

    @app.get("/boom")
    def boom() -> None:
        raise NotFoundError("internal detail that must not be exposed")

    body = TestClient(app).get("/boom").json()
    assert body["code"] == "not_found"
    assert "internal detail" not in body["message"]
    assert "Traceback" not in str(body)


def test_validation_errors_report_fields_without_leaking_internals() -> None:
    app: FastAPI = create_app()

    @app.get("/strict")
    def strict(count: int) -> dict[str, int]:
        return {"count": count}

    response = TestClient(app).get("/strict", params={"count": "not-a-number"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["fields"][0]["field"] == "count"


def test_unexpected_errors_are_generic_to_the_user() -> None:
    app: FastAPI = create_app()

    @app.get("/crash")
    def crash() -> None:
        raise RuntimeError("database password is hunter2")

    client = TestClient(app, raise_server_exceptions=False)
    body = client.get("/crash").json()
    assert body["code"] == "internal_error"
    assert "hunter2" not in str(body)


def test_domain_validation_error_maps_to_422() -> None:
    app: FastAPI = create_app()

    @app.get("/invalid")
    def invalid() -> None:
        raise ValidationError("bad input")

    assert TestClient(app).get("/invalid").status_code == 422


# ------------------------------------------------- degrading without a database


def test_the_api_starts_when_the_database_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unreachable database must not stop the application from starting.

    Most of this toolkit needs no database — the Operations Dashboard analyses
    an uploaded file end to end without one — so aborting startup would take
    down a great deal that works, in exchange for nothing.
    """
    from sqlalchemy.exc import OperationalError as _OperationalError

    import aiops_db
    from aiops_config import Settings, get_settings

    called = False

    def _explode(settings: Settings | None = None) -> None:
        nonlocal called
        called = True
        raise _OperationalError("SELECT 1", {}, Exception("connection timeout expired"))

    monkeypatch.setattr(aiops_db, "create_all", _explode)

    # Force the branch on. Without both of these the startup hook skips schema
    # creation entirely and this test would pass without exercising anything.
    settings = get_settings()
    monkeypatch.setattr(settings, "db_auto_create", True)
    monkeypatch.setattr(settings, "database_url", "postgresql://u:p@localhost:5432/db")
    assert settings.database_configured

    # Entering the client's context runs the lifespan. It must not raise.
    with TestClient(create_app()) as started:
        assert started.get("/health").status_code == 200

    assert called, "the failing schema step never ran, so nothing was proved"


def test_endpoints_that_need_no_database_still_work_without_one(
    client: TestClient,
) -> None:
    """The dashboard's analysis path never touches the database."""
    response = client.post(
        "/api/dashboard/analyse",
        files={
            "file": (
                "ops.csv",
                b"date,value\n2026-01-01,1\n2026-01-02,2\n2026-01-03,9\n",
                "text/csv",
            )
        },
    )
    assert response.status_code == 200
    assert response.json()["row_count"] == 3


def test_a_database_failure_is_a_retryable_503_not_a_generic_500(
    client: TestClient,
) -> None:
    """A driver connection failure has one cause and one fix; say which.

    'Something went wrong on our side' is true and useless. 503 also tells a
    client the request is worth retrying, which 500 does not.
    """
    from sqlalchemy.exc import OperationalError as _OperationalError

    from app.main import create_app as _create_app

    app = _create_app()

    @app.get("/boom-db")
    def _boom() -> None:
        raise _OperationalError("SELECT 1", {}, Exception("connection timeout expired"))

    with TestClient(app, raise_server_exceptions=False) as probe:
        response = probe.get("/boom-db")

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "database_unavailable"
    assert "still work" in body["message"]
    assert "traceback" not in body["message"].lower()
    assert set(body) == {"code", "message"}
