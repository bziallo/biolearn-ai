from __future__ import annotations

import hmac

import pytest
from fastapi.testclient import TestClient

from app import main as app_main
from app.core.config import get_settings
from app.core.security import _extract_token

TOKEN_ENV = "ACCESS_TOKEN"


@pytest.fixture
def secured_client(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(app_main, "recover_interrupted_tasks", lambda: None)
    monkeypatch.setenv(TOKEN_ENV, "lan-secret-token")
    get_settings.cache_clear()
    client = TestClient(app_main.create_app())
    try:
        yield client
    finally:
        get_settings.cache_clear()
        monkeypatch.delenv(TOKEN_ENV, raising=False)
        get_settings.cache_clear()


def test_health_stays_anonymous_when_token_is_required(secured_client) -> None:
    response = secured_client.get("/api/v1/health")
    assert response.status_code == 200


def test_auth_status_reports_required_without_leaking_token(secured_client) -> None:
    body = secured_client.get("/api/v1/auth").json()
    assert body == {"required": True, "authenticated": False}
    assert "lan-secret-token" not in secured_client.get("/api/v1/auth").text

    ok = secured_client.get(
        "/api/v1/auth",
        headers={"X-BioLearn-Token": "lan-secret-token"},
    ).json()
    assert ok["authenticated"] is True


def test_protected_routes_require_token(secured_client) -> None:
    unauthenticated = secured_client.get("/api/v1/subjects")
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["detail"]["code"] == "auth_required"

    wrong = secured_client.get(
        "/api/v1/subjects",
        headers={"X-BioLearn-Token": "wrong"},
    )
    assert wrong.status_code == 401

    bearer = secured_client.get(
        "/api/v1/subjects",
        headers={"Authorization": "Bearer lan-secret-token"},
    )
    assert bearer.status_code == 200

    header = secured_client.get(
        "/api/v1/subjects",
        headers={"X-BioLearn-Token": "lan-secret-token"},
    )
    assert header.status_code == 200


def test_token_never_required_for_preflight(secured_client) -> None:
    response = secured_client.options(
        "/api/v1/subjects",
        headers={
            "Origin": "https://localhost",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code in (200, 204)


def test_cors_allows_capacitor_and_configured_lan_origin(monkeypatch) -> None:
    monkeypatch.setenv("CORS_EXTRA_ORIGINS", '["http://10.61.232.199:9000"]')
    get_settings.cache_clear()
    try:
        pattern = app_main._origin_pattern(get_settings())
        import re

        assert re.fullmatch(pattern, "https://localhost")
        assert re.fullmatch(pattern, "capacitor://localhost")
        assert re.fullmatch(pattern, "http://10.61.232.199:9000")
        assert re.fullmatch(pattern, "http://127.0.0.1:5173")
        assert not re.fullmatch(pattern, "https://evil.example.com")
    finally:
        get_settings.cache_clear()


def test_extract_token_prefers_header_then_bearer() -> None:
    scope = {
        "type": "http",
        "headers": [
            (b"authorization", b"Bearer from-bearer"),
            (b"x-biolearn-token", b"from-header"),
        ],
    }
    from starlette.requests import Request

    request = Request(scope)
    assert _extract_token(request) == "from-header"

    scope["headers"] = [(b"authorization", b"Bearer only-bearer")]
    assert hmac.compare_digest(_extract_token(Request(scope)), "only-bearer")
