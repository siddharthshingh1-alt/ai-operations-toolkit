"""HTTP-contract tests for the SOP routes.

These exist because of a bug that unit tests could not catch: `get_db` used to
take a `Settings` parameter, and FastAPI — which resolves a dependency's own
parameters recursively — read that Pydantic annotation as a *second request
body field*. Every route silently began expecting `{"request": {...}}` instead
of `{...}`.

The domain logic was correct throughout. Only a test that inspects the actual
HTTP contract catches it, so that is what these do. No network, no database.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    """A client that reports server errors as responses rather than raising.

    These tests assert on the HTTP *contract* — which status code a given body
    produces. Whether a route then succeeds depends on a reachable database,
    which a unit test must not require: with the default
    `raise_server_exceptions=True`, a database that is merely slow or
    unreachable propagates as an exception and the test fails for a reason
    that has nothing to do with what it is checking.
    """
    return TestClient(create_app(), raise_server_exceptions=False)


def _request_body_schema(client: TestClient, path: str, method: str = "post") -> dict:
    """The JSON schema of a route's request body, from the OpenAPI document."""
    spec = client.get("/openapi.json").json()
    body = spec["paths"][path][method]["requestBody"]
    return body["content"]["application/json"]["schema"]


def _resolve(spec: dict, schema: dict) -> dict:
    """Follow a `$ref` into the components section."""
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return spec["components"]["schemas"][name]
    return schema


@pytest.mark.parametrize(
    ("path", "expected_fields"),
    [
        ("/api/sop/generate", {"process_description"}),
        ("/api/sop/search/ask", {"question"}),
        ("/api/sop", {"content"}),
    ],
)
def test_post_routes_take_a_flat_body(
    client: TestClient, path: str, expected_fields: set[str]
) -> None:
    """The body must be the model itself, not wrapped in an extra object.

    If FastAPI ever embeds again, the schema gains a wrapper property and the
    expected field disappears from the top level — which is exactly what this
    asserts against.
    """
    spec = client.get("/openapi.json").json()
    schema = _resolve(spec, _request_body_schema(client, path))
    properties = set(schema.get("properties", {}))

    assert expected_fields <= properties, (
        f"{path} expects a wrapped body {properties} — a dependency is being "
        "read as a request body field."
    )
    # These names would only appear if a dependency leaked into the body.
    assert "request" not in properties
    assert "settings" not in properties
    assert "db" not in properties


def test_ask_rejects_a_wrapped_body(client: TestClient) -> None:
    """The shape the bug required must now be refused."""
    response = client.post("/api/sop/search/ask", json={"request": {"question": "x y z"}})
    assert response.status_code == 422


def test_ask_accepts_a_flat_body(client: TestClient) -> None:
    """A correct body must get past validation.

    What happens after validation depends on the database, which this test
    deliberately does not require — 422 is the only status that would mean the
    contract itself is wrong.
    """
    response = client.post("/api/sop/search/ask", json={"question": "How do we handle delays?"})
    assert response.status_code != 422


def test_generate_validates_a_too_short_description(client: TestClient) -> None:
    response = client.post("/api/sop/generate", json={"process_description": "short"})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_generate_reports_the_offending_field(client: TestClient) -> None:
    """Section 23: an error message a person can act on."""
    body = client.post("/api/sop/generate", json={}).json()
    assert body["code"] == "validation_error"
    assert any("process_description" in f["field"] for f in body["fields"])


def test_every_sop_route_is_registered(client: TestClient) -> None:
    """A router that fails to mount would otherwise 404 silently."""
    paths = set(client.get("/openapi.json").json()["paths"])
    for expected in (
        "/api/sop",
        "/api/sop/generate",
        "/api/sop/extract",
        "/api/sop/{sop_id}",
        "/api/sop/{sop_id}/versions",
        "/api/sop/{sop_id}/diff",
        "/api/sop/{sop_id}/export",
        "/api/sop/search/query",
        "/api/sop/search/ask",
    ):
        assert expected in paths, f"{expected} is not mounted"


def test_diff_requires_both_versions(client: TestClient) -> None:
    assert client.get("/api/sop/sop_x/diff?from=1").status_code == 422
    assert client.get("/api/sop/sop_x/diff").status_code == 422


def test_export_rejects_an_unknown_format(client: TestClient) -> None:
    response = client.get("/api/sop/sop_x/export?format=powerpoint")
    assert response.status_code == 422
