from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.services import documents as document_service
from app.services.parsing import ParsedDocument


def create_subject(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/subjects",
        json={"name": "生物化学", "description": "蛋白质与代谢"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_chapter(client: TestClient, subject_id: str, name: str = "蛋白质") -> dict:
    response = client.post(
        f"/api/v1/subjects/{subject_id}/chapters",
        json={"name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def document_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_settings: Settings,
):
    monkeypatch.setattr(
        document_service,
        "get_settings",
        lambda: app_settings,
    )
    real_process = document_service.process_document
    monkeypatch.setattr(
        document_service,
        "process_document",
        lambda *_args, **_kwargs: None,
    )
    return real_process


def upload(
    client: TestClient,
    subject_id: str,
    *,
    filename: str = "notes.txt",
    content: bytes = b"# \xe8\x9b\x8b\xe7\x99\xbd\xe8\xb4\xa8\n\n\xe5\x86\x85\xe5\xae\xb9",
    name: str = "蛋白质笔记",
    chapter_id: str | None = None,
    force: bool = False,
):
    data = {"subject_id": subject_id, "name": name}
    if chapter_id:
        data["chapter_id"] = chapter_id
    if force:
        data["force"] = "true"
    return client.post(
        "/api/v1/documents",
        data=data,
        files={"file": (filename, content, "application/octet-stream")},
    )


def test_upload_parse_list_and_detail(
    client: TestClient,
    session_factory,
    app_settings: Settings,
    document_environment,
) -> None:
    subject = create_subject(client)
    chapter = create_chapter(client, subject["id"])

    response = upload(
        client,
        subject["id"],
        filename="蛋白质.md",
        content="# 蛋白质\n\n## 一级结构\n\n氨基酸序列。\n\n- 肽键\n".encode("utf-8"),
        name="蛋白质讲义",
        chapter_id=chapter["id"],
    )
    assert response.status_code == 201, response.text
    document = response.json()
    assert document["status"] == "uploaded"
    assert document["original_filename"] == "蛋白质.md"
    assert document["mime_type"] == "text/markdown"

    document_environment(
        document["id"],
        session_factory=session_factory,
        settings=app_settings,
    )

    response = client.get(f"/api/v1/documents/{document['id']}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["status"] == "parsed"
    assert detail["chapter_name"] == "蛋白质"
    assert detail["chunk_count"] >= 1
    assert detail["chunks"][0]["heading_path"] == "蛋白质"
    assert detail["chunks"][0]["location_label"]

    response = client.get(
        "/api/v1/documents",
        params={"subject_id": subject["id"], "status": "parsed"},
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [document["id"]]


def test_upload_rejects_bad_files_and_duplicates(
    client: TestClient,
    app_settings: Settings,
    document_environment,
) -> None:
    subject = create_subject(client)
    subject_id = subject["id"]

    response = upload(client, subject_id, filename="bad.exe", content=b"binary")
    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "unsupported_file_type"

    response = upload(client, subject_id, filename="empty.txt", content=b"")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "empty_file"

    response = upload(client, subject_id, filename="fake.pdf", content=b"not a pdf")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "file_content_mismatch"

    oversized = b"x" * (app_settings.max_upload_bytes + 1)
    response = upload(client, subject_id, filename="large.txt", content=oversized)
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "file_too_large"

    payload = "同样的内容".encode("utf-8")
    first = upload(client, subject_id, content=payload)
    assert first.status_code == 201
    second = upload(client, subject_id, content=payload)
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "duplicate_document"
    forced = upload(client, subject_id, content=payload, force=True)
    assert forced.status_code == 201


def test_upload_rejects_cross_subject_chapter(
    client: TestClient,
    document_environment,
) -> None:
    subject_a = create_subject(client)
    subject_b = create_subject(client)
    chapter_b = create_chapter(client, subject_b["id"])

    response = upload(
        client,
        subject_a["id"],
        chapter_id=chapter_b["id"],
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "chapter_subject_mismatch"


def test_storage_path_is_safe_and_delete_guard(
    client: TestClient,
    session_factory,
    app_settings: Settings,
    document_environment,
) -> None:
    subject = create_subject(client)
    response = upload(
        client,
        subject["id"],
        filename="../../evil.txt",
        content=b"safe content",
    )
    assert response.status_code == 201
    document = response.json()

    with session_factory() as db:
        from app.models import Document

        stored = db.get(Document, document["id"])
        assert stored is not None
        assert ".." not in stored.storage_name
        root = Path(app_settings.upload_dir).resolve()
        stored_path = (root / stored.storage_name).resolve()
        assert root in stored_path.parents
        assert stored_path.exists()

    point_response = client.post(
        "/api/v1/knowledge-points",
        json={
            "document_id": document["id"],
            "name": "安全测试知识点",
            "explanation": "用于删除保护测试。",
        },
    )
    assert point_response.status_code == 201, point_response.text

    response = client.delete(f"/api/v1/documents/{document['id']}")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "document_has_knowledge_points"

    response = client.delete(
        f"/api/v1/documents/{document['id']}",
        params={"cascade": "true"},
    )
    assert response.status_code == 204
    assert client.get(f"/api/v1/documents/{document['id']}").status_code == 404
    assert not stored_path.exists()


def test_parse_failure_needs_ocr_and_retry(
    client: TestClient,
    session_factory,
    app_settings: Settings,
    document_environment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subject = create_subject(client)
    document = upload(
        client,
        subject["id"],
        filename="scan.pdf",
        content=b"%PDF-1.4\n% fake scan",
    ).json()

    monkeypatch.setattr(
        document_service,
        "parse_document",
        lambda *_args, **_kwargs: ParsedDocument(
            title="扫描件",
            blocks=[],
            page_count=1,
            warnings=["没有提取到文字"],
            needs_ocr=True,
        ),
    )
    document_environment(
        document["id"],
        session_factory=session_factory,
        settings=app_settings,
    )
    detail = client.get(f"/api/v1/documents/{document['id']}").json()
    assert detail["status"] == "needs_ocr"
    assert "OCR" in detail["parse_error"]

    monkeypatch.setattr(
        document_service,
        "parse_document",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("corrupt document")
        ),
    )
    response = client.post(f"/api/v1/documents/{document['id']}/retry-parse")
    assert response.status_code == 200
    document_environment(
        document["id"],
        session_factory=session_factory,
        settings=app_settings,
    )
    detail = client.get(f"/api/v1/documents/{document['id']}").json()
    assert detail["status"] == "failed"
    assert detail["parse_error"]


def test_retry_parse_protects_parsed_documents_and_existing_points(
    client: TestClient,
    session_factory,
    app_settings: Settings,
    document_environment,
) -> None:
    subject = create_subject(client)
    document = upload(
        client,
        subject["id"],
        filename="retry.md",
        content="# 蛋白质\n\n一级结构是氨基酸序列。\n".encode("utf-8"),
    ).json()
    document_environment(
        document["id"],
        session_factory=session_factory,
        settings=app_settings,
    )

    parsed = client.get(f"/api/v1/documents/{document['id']}").json()
    assert parsed["status"] == "parsed"
    original_chunk_count = parsed["chunk_count"]

    # A successfully parsed document is not silently reparsed, because that
    # would delete its chunks and detach any knowledge-point sources.
    response = client.post(f"/api/v1/documents/{document['id']}/retry-parse")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "document_already_parsed"
    assert (
        client.get(f"/api/v1/documents/{document['id']}").json()["chunk_count"]
        == original_chunk_count
    )

    point = client.post(
        "/api/v1/knowledge-points",
        json={
            "document_id": document["id"],
            "name": "一级结构",
            "explanation": "氨基酸序列。",
        },
    )
    assert point.status_code == 201, point.text

    # Even a failed document cannot be reparsed while it still has knowledge
    # points; deleting the old chunks would null their source_chunk_id.
    with session_factory() as db:
        from app.models import Document

        stored = db.get(Document, document["id"])
        assert stored is not None
        stored.status = "failed"
        db.commit()

    response = client.post(f"/api/v1/documents/{document['id']}/retry-parse")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "document_has_knowledge_points"
    assert (
        client.get(f"/api/v1/documents/{document['id']}").json()["chunk_count"]
        == original_chunk_count
    )

    # Removing the point makes a genuine failed-parse retry possible again.
    assert (
        client.delete(
            f"/api/v1/knowledge-points/{point.json()['id']}"
        ).status_code
        == 204
    )
    response = client.post(f"/api/v1/documents/{document['id']}/retry-parse")
    assert response.status_code == 200
    assert response.json()["status"] == "uploaded"
