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
