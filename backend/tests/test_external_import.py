from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.models import (
    Chapter,
    Document,
    ImportJob,
    KnowledgeExtractionJob,
    KnowledgePoint,
)
from app.schemas.external_import import ExternalImportPayload
from app.services import external_import as external_service
from app.services import importing as import_service


@pytest.fixture
def external_env(monkeypatch: pytest.MonkeyPatch, app_settings: Settings):
    monkeypatch.setattr(external_service, "get_settings", lambda: app_settings)
    return app_settings


def create_subject(client: TestClient, name: str = "生物化学") -> dict:
    response = client.post("/api/v1/subjects", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def make_payload(
    *,
    subject_name: str = "生物化学",
    document_name: str = "蛋白质讲义",
    points: list[dict] | None = None,
    chapter_tree: list[dict] | None = None,
    version: str = "1.0",
) -> dict:
    return {
        "schema_version": version,
        "document": {
            "name": document_name,
            "type": "pptx",
            "summary": "蛋白质结构与功能",
        },
        "subject": {"id": None, "name": subject_name},
        "chapter_tree": chapter_tree
        if chapter_tree is not None
        else [
            {
                "id": "ch1",
                "name": "第一章 蛋白质",
                "source_slide": 2,
                "children": [
                    {
                        "id": "ch1-1",
                        "name": "第一节 一级结构",
                        "source_slide": 5,
                        "children": [],
                    }
                ],
            }
        ],
        "knowledge_points": points
        if points is not None
        else [
            {
                "point_id": "kp-001",
                "title": "蛋白质一级结构",
                "content": "蛋白质的一级结构是氨基酸的线性排列顺序。",
                "chapter_path": ["第一章 蛋白质", "第一节 一级结构"],
                "category": "structure",
                "importance": "high",
                "key_terms": ["氨基酸序列", "肽键"],
                "source": {
                    "document_name": "蛋白质讲义",
                    "slide": 5,
                    "quote": "蛋白质的一级结构是氨基酸的排列顺序。",
                },
                "prerequisites": ["氨基酸"],
                "confidence": 0.9,
            }
        ],
        "metadata": {
            "model": "external-ai",
            "generated_at": "2026-10-19T12:00:00Z",
            "shard_index": 1,
            "shard_total": 1,
        },
    }


def upload_external(
    client: TestClient,
    payload: dict | str,
    *,
    subject_id: str | None,
    duplicate_strategy: str = "skip",
    filename: str = "external.json",
) -> dict:
    content = payload if isinstance(payload, str) else json.dumps(
        payload, ensure_ascii=False
    )
    data = {"duplicate_strategy": duplicate_strategy}
    if subject_id:
        data["subject_id"] = subject_id
    response = client.post(
        "/api/v1/imports/external",
        data=data,
        files={"file": (filename, content.encode("utf-8"), "application/json")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def confirm_external(
    client: TestClient,
    import_id: str,
    *,
    accept: bool = True,
    chapter_id: str | None = None,
) -> dict:
    response = client.post(
        f"/api/v1/imports/{import_id}/confirm",
        json={
            "accept_suggestions": accept,
            "chapter_id": chapter_id,
            "create_missing": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def chapter_names(client: TestClient, subject_id: str) -> list[str]:
    tree = client.get(f"/api/v1/subjects/{subject_id}/chapters").json()
    names: list[str] = []

    def walk(nodes: list[dict]) -> None:
        for node in nodes:
            names.append(node["name"])
            walk(node.get("children", []))

    walk(tree)
    return names


def test_valid_external_json_import_creates_pending_points(
    client: TestClient,
    session_factory,
    app_settings: Settings,
    external_env,
) -> None:
    subject = create_subject(client)
    imported = upload_external(client, make_payload(), subject_id=subject["id"])
    assert imported["status"] == "awaiting_confirmation"
    assert imported["source_type"] == "external_json"
    suggestion = imported["suggestion"]
    assert suggestion["knowledge_point_count"] == 1
    assert suggestion["points_preview"][0]["source_slide"] == 5

    completed = confirm_external(client, imported["id"])
    assert completed["status"] == "completed"
    assert completed["result"]["created_point_count"] == 1
    assert completed["result"]["chapter_id"]

    with session_factory() as db:
        document = db.get(Document, completed["document_id"])
        assert document is not None
        assert document.status == "parsed"
        assert document.chapter_id
        points = (
            db.query(KnowledgePoint)
            .filter(KnowledgePoint.document_id == document.id)
            .all()
        )
        assert len(points) == 1
        point = points[0]
        assert point.name == "蛋白质一级结构"
        assert point.review_status == "pending"
        assert point.origin == "ai"
        assert point.needs_review is True
        assert point.importance == "high"
        assert point.prerequisites == ["氨基酸"]
        assert point.external_id == "kp-001"
        assert point.source_slide == 5
        assert point.source_quote_verified is False
        jobs = (
            db.query(KnowledgeExtractionJob)
            .filter(KnowledgeExtractionJob.document_id == document.id)
            .count()
        )
        assert jobs == 0

    assert "第一章 蛋白质" in chapter_names(client, subject["id"])
    assert "第一节 一级结构" in chapter_names(client, subject["id"])


def test_external_json_validation_errors(
    client: TestClient,
    app_settings: Settings,
    external_env,
) -> None:
    subject = create_subject(client)

    response = client.post(
        "/api/v1/imports/external",
        data={"subject_id": subject["id"]},
        files={"file": ("bad.json", b"{not json", "application/json")},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_json"

    response = client.post(
        "/api/v1/imports/external",
        data={"subject_id": subject["id"]},
        files={
            "file": (
                "bad.txt",
                b"{}",
                "text/plain",
            )
        },
    )
    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "external_json_required"

    unknown = make_payload(version="9.9")
    response = client.post(
        "/api/v1/imports/external",
        data={"subject_id": subject["id"]},
        files={
            "file": (
                "unknown.json",
                json.dumps(unknown).encode("utf-8"),
                "application/json",
            )
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "external_json_invalid"
    assert "schema_version" in response.json()["detail"]["message"]

    broken = make_payload()
    broken["knowledge_points"] = [{"title": "缺少内容"}]
    response = client.post(
        "/api/v1/imports/external",
        data={"subject_id": subject["id"]},
        files={
            "file": (
                "broken.json",
                json.dumps(broken).encode("utf-8"),
                "application/json",
            )
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "external_json_invalid"

    oversized = make_payload()
    oversized["document"]["summary"] = "x" * (app_settings.max_upload_bytes + 100)
    response = client.post(
        "/api/v1/imports/external",
        data={"subject_id": subject["id"]},
        files={
            "file": (
                "huge.json",
                json.dumps(oversized).encode("utf-8"),
                "application/json",
            )
        },
    )
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "file_too_large"


def test_external_import_matches_existing_chapter_and_skips_duplicate_import(
    client: TestClient,
    session_factory,
    app_settings: Settings,
    external_env,
) -> None:
    subject = create_subject(client)
    root = client.post(
        f"/api/v1/subjects/{subject['id']}/chapters",
        json={"name": "蛋白质讲义"},
    )
    assert root.status_code == 201

    payload = make_payload()
    first = upload_external(client, payload, subject_id=subject["id"])
    first_done = confirm_external(client, first["id"])
    assert root.json()["id"] in first_done["result"]["reused_chapter_ids"]
    assert chapter_names(client, subject["id"]).count("蛋白质讲义") == 1

    second = upload_external(client, payload, subject_id=subject["id"])
    assert second["status"] == "awaiting_confirmation"
    assert second["suggestion"]["duplicate_import"] is True
    second_done = confirm_external(client, second["id"])
    assert second_done["status"] == "completed"
    assert second_done["result"]["skipped_point_count"] == 1
    assert second_done["result"]["created_point_count"] == 0

    with session_factory() as db:
        assert (
            db.query(KnowledgePoint)
            .filter(KnowledgePoint.document_id == first_done["document_id"])
            .count()
            == 1
        )


def test_external_import_can_archive_to_selected_chapter(
    client: TestClient,
    session_factory,
    app_settings: Settings,
    external_env,
) -> None:
    subject = create_subject(client)
    selected = client.post(
        f"/api/v1/subjects/{subject['id']}/chapters",
        json={"name": "指定归档章节"},
    )
    assert selected.status_code == 201
    imported = upload_external(client, make_payload(), subject_id=subject["id"])
    response = client.post(
        f"/api/v1/imports/{imported['id']}/confirm",
        json={
            "accept_suggestions": False,
            "chapter_id": selected.json()["id"],
            "create_missing": False,
        },
    )
    assert response.status_code == 200, response.text
    done = response.json()
    assert done["result"]["chapter_id"] == selected.json()["id"]
    assert done["result"]["created_chapter_ids"] == []
    with session_factory() as db:
        points = (
            db.query(KnowledgePoint)
            .filter(KnowledgePoint.document_id == done["document_id"])
            .all()
        )
        assert points
        assert all(
            point.chapter_id == selected.json()["id"] for point in points
        )
    assert chapter_names(client, subject["id"]).count("第一章 蛋白质") == 0


def test_external_update_pending_does_not_overwrite_approved(
    client: TestClient,
    session_factory,
    app_settings: Settings,
    external_env,
) -> None:
    subject = create_subject(client)
    first = upload_external(client, make_payload(), subject_id=subject["id"])
    done = confirm_external(client, first["id"])
    points = client.get(
        f"/api/v1/documents/{done['document_id']}/knowledge-points"
    ).json()["points"]
    point = points[0]
    approved = client.post(
        f"/api/v1/knowledge-points/{point['id']}/review",
        json={"status": "approved"},
    )
    assert approved.status_code == 200

    second = upload_external(
        client,
        make_payload(),
        subject_id=subject["id"],
        duplicate_strategy="update_pending",
    )
    done2 = confirm_external(client, second["id"])
    assert done2["result"]["updated_point_count"] == 0
    assert done2["result"]["skipped_point_count"] == 1

    detail = client.get(f"/api/v1/knowledge-points/{point['id']}").json()
    assert detail["review_status"] == "approved"
    assert detail["explanation"] == point["explanation"]


def test_external_missing_source_is_flagged_but_importable(
    client: TestClient,
    session_factory,
    app_settings: Settings,
    external_env,
) -> None:
    subject = create_subject(client)
    payload = make_payload(
        points=[
            {
                "title": "无来源知识点",
                "content": "内容仍然可以导入，但必须等待人工核验。",
                "chapter_path": [],
                "category": "基本概念",
                "source": {},
            }
        ]
    )
    imported = upload_external(client, payload, subject_id=subject["id"])
    assert imported["suggestion"]["missing_source_count"] == 1
    assert imported["suggestion"]["points_preview"][0]["warnings"]
    done = confirm_external(client, imported["id"])
    with session_factory() as db:
        point = (
            db.query(KnowledgePoint)
            .filter(KnowledgePoint.document_id == done["document_id"])
            .one()
        )
        assert point.needs_review is True
        assert "未提供来源" in (point.source_locator or "")
        assert point.review_status == "pending"


def test_external_import_rolls_back_chapters_and_points_on_failure(
    client: TestClient,
    session_factory,
    app_settings: Settings,
    external_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subject = create_subject(client)
    imported = upload_external(client, make_payload(), subject_id=subject["id"])

    calls = {"count": 0}
    original = import_service._next_sort_order

    def failing_next_sort_order(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] >= 2:
            raise RuntimeError("simulated external archive failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(
        import_service,
        "_next_sort_order",
        failing_next_sort_order,
    )
    response = client.post(
        f"/api/v1/imports/{imported['id']}/confirm",
        json={"accept_suggestions": True, "create_missing": True},
    )
    assert response.status_code == 500
    job = client.get(f"/api/v1/imports/{imported['id']}").json()
    assert job["status"] == "failed"
    assert job["error"]
    assert chapter_names(client, subject["id"]) == []
    with session_factory() as db:
        document = db.get(Document, imported["document_id"])
        assert document is not None
        assert (
            db.query(KnowledgePoint)
            .filter(KnowledgePoint.document_id == document.id)
            .count()
            == 0
        )

    retry = client.post(f"/api/v1/imports/{imported['id']}/retry")
    assert retry.status_code == 200
    assert retry.json()["status"] == "awaiting_confirmation"


def test_external_subject_override_and_template(
    client: TestClient,
    external_env,
) -> None:
    subject = create_subject(client, "分子生物学")
    payload = make_payload(subject_name="不存在的学科")
    imported = upload_external(
        client,
        payload,
        subject_id=subject["id"],
    )
    assert imported["suggestion"]["subject_id"] == subject["id"]

    template = client.get("/api/v1/imports/external/template")
    assert template.status_code == 200
    body = template.json()
    assert body["schema_version"] == "1.0"
    assert "schema_version" in body["prompt"]
    assert "knowledge_points" in body["prompt"]
    assert body["json_schema"]["properties"]["knowledge_points"]
    ExternalImportPayload.model_validate(body["example"])


def test_external_large_payload_and_shards_metadata(
    client: TestClient,
    session_factory,
    app_settings: Settings,
    external_env,
) -> None:
    subject = create_subject(client)
    points = [
        {
            "point_id": f"kp-{index}",
            "title": f"知识点 {index}",
            "content": f"内容 {index}",
            "chapter_path": ["第一章 蛋白质"],
            "category": "basic_concept",
            "importance": "medium",
            "key_terms": [f"术语 {index}"],
            "source": {"slide": 2},
        }
        for index in range(200)
    ]
    payload = make_payload(points=points)
    payload["metadata"]["shard_index"] = 1
    payload["metadata"]["shard_total"] = 3
    imported = upload_external(client, payload, subject_id=subject["id"])
    assert imported["suggestion"]["knowledge_point_count"] == 200
    done = confirm_external(client, imported["id"])
    assert done["result"]["created_point_count"] == 200
    with session_factory() as db:
        assert (
            db.query(KnowledgePoint)
            .filter(KnowledgePoint.document_id == done["document_id"])
            .count()
            == 200
        )
