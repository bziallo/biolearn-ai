from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app import main as app_main


def _client_for_dist(tmp_path: Path, monkeypatch) -> TestClient:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div>spa</div>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")

    settings = app_main.get_settings().model_copy(
        update={
            "serve_frontend": True,
            "frontend_dist_dir": dist,
        }
    )
    monkeypatch.setattr(app_main, "get_settings", lambda: settings)
    monkeypatch.setattr(app_main, "recover_interrupted_tasks", lambda: None)
    return TestClient(app_main.create_app())


def test_spa_is_served_with_api_and_static_assets(tmp_path: Path, monkeypatch) -> None:
    client = _client_for_dist(tmp_path, monkeypatch)

    root = client.get("/")
    assert root.status_code == 200
    assert "spa" in root.text

    deep_link = client.get("/practice")
    assert deep_link.status_code == 200
    assert "spa" in deep_link.text

    asset = client.get("/assets/app.js")
    assert asset.status_code == 200
    assert "ok" in asset.text

    health = client.get("/api/v1/health")
    assert health.status_code == 200

    missing_api = client.get("/api/v1/definitely-missing")
    assert missing_api.status_code == 404

    missing_reserved = client.get("/health")
    assert missing_reserved.status_code == 404


def test_spa_mount_is_skipped_without_build(tmp_path: Path, monkeypatch) -> None:
    settings = app_main.get_settings().model_copy(
        update={
            "serve_frontend": True,
            "frontend_dist_dir": tmp_path / "missing-dist",
        }
    )
    monkeypatch.setattr(app_main, "get_settings", lambda: settings)
    monkeypatch.setattr(app_main, "recover_interrupted_tasks", lambda: None)
    client = TestClient(app_main.create_app())

    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/").status_code == 404
