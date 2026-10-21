from fastapi.testclient import TestClient

from app.core.config import get_settings


def test_health_returns_service_metadata(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    settings = get_settings()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": settings.app_name,
        "version": "0.1.0",
        "environment": settings.app_env,
    }


def test_health_is_not_exposed_without_version_prefix(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 404
