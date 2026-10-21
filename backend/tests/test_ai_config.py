from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings


def _unconfigured_settings(settings: Settings, path: Path) -> Settings:
    return settings.model_copy(
        update={
            "ai_api_base": "",
            "ai_api_key": None,
            "ai_model": "",
            "ai_config_path": path,
        }
    )


def test_ai_key_is_saved_server_side_and_never_returned(
    client: TestClient,
    app_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_settings = _unconfigured_settings(
        app_settings,
        tmp_path / "runtime-ai.json",
    )
    monkeypatch.setattr(
        "app.services.ai_config.get_settings",
        lambda: config_settings,
    )

    response = client.put(
        "/api/v1/ai/config",
        json={
            "provider": "openai-compatible",
            "api_base": "http://ai.example/v1",
            "model": "example-model",
            "api_key": "secret-key",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["configured"] is True
    assert payload["key_configured"] is True
    assert payload["source"] == "runtime"
    assert payload["model"] == "example-model"
    assert "secret-key" not in response.text
    assert config_settings.ai_config_path.exists()

    status = client.get("/api/v1/ai/status")
    assert status.status_code == 200
    assert status.json()["configured"] is True
    assert "secret-key" not in status.text

    # Omitting the key preserves the stored value.
    response = client.put(
        "/api/v1/ai/config",
        json={
            "provider": "openai-compatible",
            "api_base": "http://ai.example/v1",
            "model": "example-model",
        },
    )
    assert response.status_code == 200
    assert response.json()["key_configured"] is True

    response = client.put(
        "/api/v1/ai/config",
        json={
            "provider": "openai-compatible",
            "api_base": "http://ai.example/v1",
            "model": "example-model",
            "clear_key": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["key_configured"] is False

    response = client.delete("/api/v1/ai/config")
    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["source"] == "unconfigured"
    assert not config_settings.ai_config_path.exists()
