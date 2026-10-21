from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import DomainError
from app.db.base import utc_now
from app.models import Chapter, Document, DocumentChunk, KnowledgePoint, Subject
from app.services import knowledge as knowledge_service
from app.services import knowledge_review
from app.services import job_control
from app.services.ai_client import AIClientCancelled, AIClientError
from app.services.recovery import recover_interrupted_tasks


class FakeAI:
    def __init__(self, responses: list[dict | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def chat_json(self, system_prompt: str, user_prompt: str, *, cancel_check=None) -> dict:
        self.calls.append((system_prompt, user_prompt))
        if cancel_check is not None and cancel_check():
            raise AIClientCancelled()
        if not self.responses:
            raise AIClientError("fake AI 没有更多响应")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


ANALYSIS = {
    "theme": "蛋白质的结构与功能",
    "learning_objectives": ["理解一级结构"],
    "sections": ["蛋白质一级结构"],
    "core_concepts": ["氨基酸序列"],
    "processes": ["肽键形成"],
    "relationships": ["序列决定结构"],
    "formulas": [],
    "confusions": [],
    "prerequisites": ["氨基酸"],
    "cross_links": [],
}

EXTRACTION = {
    "points": [
        {
            "name": "蛋白质一级结构",
            "type": "structure",
            "explanation": "蛋白质的一级结构是氨基酸的线性排列顺序。",
            "core_points": ["氨基酸序列", "肽键连接"],
            "conditions": None,
            "source_quote": "蛋白质由氨基酸通过肽键连接。",
            "confidence": 0.92,
            "needs_review": False,
            "parent_name": None,
        }
    ]
}

MERGE = {
    "merged_points": [
        {
            "ref": "m1",
            "name": "蛋白质一级结构",
            "type": "structure",
            "explanation": "蛋白质的一级结构是氨基酸的线性排列顺序。",
            "core_points": ["氨基酸序列", "肽键连接"],
            "conditions": None,
            "parent_ref": None,
            "source_point_ids": [1],
            "confidence": 0.92,
            "needs_review": False,
            "conflict_note": None,
        }
    ]
}


def make_document(
    session_factory,
    *,
    name: str = "蛋白质讲义",
    chunk_content: str = "蛋白质由氨基酸通过肽键连接。一级结构决定空间结构。",
) -> tuple[str, str]:
    with session_factory() as db:
        subject = Subject(name="生物化学", description="测试学科")
        db.add(subject)
        db.flush()
        chapter = Chapter(
            subject_id=subject.id,
            name="蛋白质",
            description="蛋白质章节",
        )
        db.add(chapter)
        db.flush()
        document = Document(
            subject_id=subject.id,
            chapter_id=chapter.id,
            name=name,
            content_title="蛋白质的分子结构",
            original_filename="protein.txt",
            storage_name="fake.txt",
            mime_type="text/plain",
            extension=".txt",
            size_bytes=100,
            sha256="a" * 64,
            status="parsed",
            page_count=1,
            parsed_at=utc_now(),
        )
        db.add(document)
        db.flush()
        chunk = DocumentChunk(
            document_id=document.id,
            chunk_index=0,
            heading_path="蛋白质",
            heading_level=1,
            content=chunk_content,
            page_start=1,
            page_end=1,
            char_start=0,
            char_end=len(chunk_content),
            block_start=0,
            block_end=1,
            location_label="第 1 页",
        )
        db.add(chunk)
        db.commit()
        return document.id, chunk.id


def test_ai_status_is_safe_without_key(client: TestClient) -> None:
    response = client.get("/api/v1/ai/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is False
    assert "api_key" not in payload
    assert "AI 未配置" in payload["message"]


def test_ai_connection_test_reports_missing_configuration(
    client: TestClient,
) -> None:
    response = client.post("/api/v1/ai/test")
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "ai_connection_failed"
    assert "AI 未配置" in response.json()["detail"]["message"]


def test_extraction_requires_configuration(
    client: TestClient,
    session_factory,
) -> None:
    document_id, _ = make_document(session_factory)
    response = client.post(f"/api/v1/documents/{document_id}/extract")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "ai_not_configured"


def test_full_extraction_flow_and_review(
    client: TestClient,
    session_factory,
    app_settings: Settings,
) -> None:
    document_id, chunk_id = make_document(session_factory)
    fake = FakeAI([ANALYSIS, EXTRACTION, MERGE])

    job = knowledge_service.create_extraction_job(
        session_factory(),
        document_id,
        settings=app_settings,
    )
    knowledge_service.run_extraction(
        job.id,
        session_factory=session_factory,
        client=fake,
        settings=app_settings,
    )

    response = client.get(f"/api/v1/knowledge-jobs/{job.id}")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["progress"] == 100
    assert response.json()["extracted_count"] == 1

    response = client.get(f"/api/v1/documents/{document_id}/knowledge-points")
    assert response.status_code == 200
    payload = response.json()
    assert payload["stats"]["pending"] == 1
    assert payload["stats"]["approved"] == 0
    assert len(payload["points"]) == 1
    point = payload["points"][0]
    assert point["name"] == "蛋白质一级结构"
    assert point["source_quote_verified"] is True
    assert point["source_chunk_id"] == chunk_id
    assert point["source_page"] == 1

    response = client.post(
        f"/api/v1/knowledge-points/{point['id']}/review",
        json={"status": "approved"},
    )
    assert response.status_code == 200
    assert response.json()["review_status"] == "approved"
    assert response.json()["published_at"]

    # A second extraction must preserve the approved point and flag the new
    # matching draft instead of overwriting human-reviewed content.
    fake2 = FakeAI([ANALYSIS, EXTRACTION, MERGE])
    job2 = knowledge_service.create_extraction_job(
        session_factory(),
        document_id,
        settings=app_settings,
    )
    knowledge_service.run_extraction(
        job2.id,
        session_factory=session_factory,
        client=fake2,
        settings=app_settings,
    )
    payload = client.get(
        f"/api/v1/documents/{document_id}/knowledge-points"
    ).json()
    assert payload["stats"]["approved"] == 1
    assert payload["stats"]["duplicates"] == 1
    assert payload["stats"]["total"] == 2


def test_ai_failure_and_retry(
    client: TestClient,
    session_factory,
    app_settings: Settings,
) -> None:
    document_id, _ = make_document(session_factory)
    job = knowledge_service.create_extraction_job(
        session_factory(),
        document_id,
        settings=app_settings,
    )
    knowledge_service.run_extraction(
        job.id,
        session_factory=session_factory,
        client=FakeAI([AIClientError("模拟 AI 调用失败")]),
        settings=app_settings,
    )
    failed = client.get(f"/api/v1/knowledge-jobs/{job.id}").json()
    assert failed["status"] == "failed"
    assert "模拟 AI" in failed["error"]

    retry = knowledge_service.retry_extraction(
        session_factory(),
        job.id,
        settings=app_settings,
    )
    assert retry.attempts == 2
    knowledge_service.run_extraction(
        retry.id,
        session_factory=session_factory,
        client=FakeAI([ANALYSIS, EXTRACTION, MERGE]),
        settings=app_settings,
    )
    completed = client.get(f"/api/v1/knowledge-jobs/{retry.id}").json()
    assert completed["status"] == "completed"


def test_cancel_queued_job_and_reject_completed_job(
    client: TestClient,
    session_factory,
    app_settings: Settings,
) -> None:
    document_id, _ = make_document(session_factory)
    queued = knowledge_service.create_extraction_job(
        session_factory(),
        document_id,
        settings=app_settings,
    )

    response = client.post(f"/api/v1/knowledge-jobs/{queued.id}/cancel")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "cancelled"
    assert payload["cancel_requested"] is True

    completed = knowledge_service.create_extraction_job(
        session_factory(),
        document_id,
        settings=app_settings,
    )
    knowledge_service.run_extraction(
        completed.id,
        session_factory=session_factory,
        client=FakeAI([ANALYSIS, EXTRACTION, MERGE]),
        settings=app_settings,
    )
    response = client.post(f"/api/v1/knowledge-jobs/{completed.id}/cancel")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "job_not_cancellable"


def test_cancel_during_extraction_marks_cancelled_without_drafts(
    client: TestClient,
    session_factory,
    app_settings: Settings,
) -> None:
    document_id, _ = make_document(session_factory)
    job = knowledge_service.create_extraction_job(
        session_factory(),
        document_id,
        settings=app_settings,
    )
    job_id = job.id

    class CancellingFakeAI(FakeAI):
        def chat_json(self, system_prompt, user_prompt, *, cancel_check=None):
            response = super().chat_json(
                system_prompt,
                user_prompt,
                cancel_check=cancel_check,
            )
            if len(self.calls) == 2:
                job_control.request_cancel(job_id)
            return response

    fake = CancellingFakeAI([ANALYSIS, EXTRACTION, MERGE])
    knowledge_service.run_extraction(
        job.id,
        session_factory=session_factory,
        client=fake,
        settings=app_settings,
    )

    payload = client.get(f"/api/v1/knowledge-jobs/{job.id}").json()
    assert payload["status"] == "cancelled"
    assert payload["error"] is None
    assert payload["merged_count"] == 0
    assert len(fake.calls) == 2

    knowledge = client.get(
        f"/api/v1/documents/{document_id}/knowledge-points"
    ).json()
    assert knowledge["stats"]["total"] == 0


def test_ai_invalid_output_is_rejected(
    client: TestClient,
    session_factory,
    app_settings: Settings,
) -> None:
    document_id, _ = make_document(session_factory)
    job = knowledge_service.create_extraction_job(
        session_factory(),
        document_id,
        settings=app_settings,
    )
    knowledge_service.run_extraction(
        job.id,
        session_factory=session_factory,
        client=FakeAI([ANALYSIS, {"points": [{"name": 1}]}]),
        settings=app_settings,
    )
    failed = client.get(f"/api/v1/knowledge-jobs/{job.id}").json()
    assert failed["status"] == "failed"
    assert "格式" in failed["error"]


def test_ai_merge_deduplicates_and_keeps_both_sources(
    client: TestClient,
    session_factory,
    app_settings: Settings,
) -> None:
    document_id, _ = make_document(session_factory)
    extraction = {
        "points": [
            {
                "name": "蛋白质一级结构",
                "type": "structure",
                "explanation": "氨基酸序列。",
                "core_points": ["序列"],
                "source_quote": "蛋白质由氨基酸通过肽键连接。",
                "confidence": 0.9,
                "needs_review": False,
                "parent_name": None,
            },
            {
                "name": "氨基酸排列顺序",
                "type": "structure",
                "explanation": "一级结构决定空间结构。",
                "core_points": ["顺序决定结构"],
                "source_quote": "一级结构决定空间结构。",
                "confidence": 0.8,
                "needs_review": False,
                "parent_name": None,
            },
        ]
    }
    merge = {
        "merged_points": [
            {
                "ref": "m1",
                "name": "蛋白质一级结构",
                "type": "structure",
                "explanation": "一级结构是氨基酸序列，并决定空间结构。",
                "core_points": ["序列", "顺序决定结构"],
                "conditions": None,
                "parent_ref": None,
                "source_point_ids": [1, 2],
                "confidence": 0.85,
                "needs_review": True,
                "conflict_note": "两个候选解释范围不完全一致",
            }
        ]
    }
    job = knowledge_service.create_extraction_job(
        session_factory(),
        document_id,
        settings=app_settings,
    )
    knowledge_service.run_extraction(
        job.id,
        session_factory=session_factory,
        client=FakeAI([ANALYSIS, extraction, merge]),
        settings=app_settings,
    )

    payload = client.get(
        f"/api/v1/documents/{document_id}/knowledge-points"
    ).json()
    assert payload["stats"]["total"] == 1
    point = payload["points"][0]
    assert "蛋白质由氨基酸通过肽键连接" in point["source_quote"]
    assert "一级结构决定空间结构" in point["source_quote"]
    assert point["needs_review"] is True
    assert point["review_note"]


def test_manual_review_tree_cycle_and_merge(
    client: TestClient,
    session_factory,
) -> None:
    document_id, _ = make_document(session_factory)
    first = client.post(
        "/api/v1/knowledge-points",
        json={
            "document_id": document_id,
            "name": "一级结构",
            "explanation": "氨基酸序列。",
            "core_points": ["序列"],
        },
    )
    assert first.status_code == 201, first.text
    first_point = first.json()
    second = client.post(
        "/api/v1/knowledge-points",
        json={
            "document_id": document_id,
            "name": "二级结构",
            "explanation": "局部折叠。",
            "parent_id": first_point["id"],
        },
    )
    assert second.status_code == 201, second.text
    second_point = second.json()

    cycle = client.patch(
        f"/api/v1/knowledge-points/{first_point['id']}",
        json={"parent_id": second_point["id"]},
    )
    assert cycle.status_code == 422
    assert cycle.json()["detail"]["code"] == "knowledge_point_cycle"

    merged = client.post(
        "/api/v1/knowledge-points/merge",
        json={
            "source_ids": [first_point["id"], second_point["id"]],
            "name": "蛋白质结构层级",
            "explanation": "从一级到高级结构的层级关系。",
        },
    )
    assert merged.status_code == 200, merged.text
    assert merged.json()["review_status"] == "pending"
    assert "蛋白质结构层级" == merged.json()["name"]

    bulk = client.post(
        "/api/v1/knowledge-points/bulk-review",
        json={"ids": [merged.json()["id"]], "status": "approved"},
    )
    assert bulk.status_code == 200
    assert bulk.json()["updated"] == 1
    listed = client.get(
        "/api/v1/knowledge-points",
        params={"document_id": document_id, "review_status": "approved"},
    ).json()
    assert len(listed["points"]) == 1
    assert listed["stats"]["approved"] == 1


def test_edit_approved_point_requires_re_review_and_filters(
    session_factory,
    client: TestClient,
) -> None:
    document_id, _ = make_document(session_factory)
    created = client.post(
        "/api/v1/knowledge-points",
        json={
            "document_id": document_id,
            "name": "蛋白质变性",
            "explanation": "空间结构破坏导致性质改变。",
            "type": "basic_concept",
        },
    )
    assert created.status_code == 201, created.text
    point = created.json()
    approved = client.post(
        f"/api/v1/knowledge-points/{point['id']}/review",
        json={"status": "approved"},
    )
    assert approved.status_code == 200
    assert approved.json()["published_at"]

    edited = client.patch(
        f"/api/v1/knowledge-points/{point['id']}",
        json={"explanation": "空间结构被破坏，生物活性丧失。"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["review_status"] == "pending"
    assert edited.json()["published_at"] is None
    assert edited.json()["needs_review"] is True

    filtered = client.get(
        "/api/v1/knowledge-points",
        params={
            "subject_id": point["subject_id"],
            "q": "变性",
            "point_type": "basic_concept",
            "review_status": "pending",
        },
    )
    assert filtered.status_code == 200
    payload = filtered.json()
    assert payload["total"] == 1
    assert payload["points"][0]["id"] == point["id"]


def test_knowledge_delete_guard_and_recovery(
    session_factory,
) -> None:
    document_id, _ = make_document(session_factory)
    with session_factory() as db:
        parent = KnowledgePoint(
            subject_id=db.get(Document, document_id).subject_id,
            document_id=document_id,
            name="父知识点",
            explanation="父级",
            core_points=[],
            origin="manual",
            review_status="pending",
        )
        db.add(parent)
        db.flush()
        child = KnowledgePoint(
            subject_id=parent.subject_id,
            document_id=document_id,
            parent_id=parent.id,
            name="子知识点",
            explanation="子级",
            core_points=[],
            origin="manual",
            review_status="pending",
        )
        db.add(child)
        db.commit()
        parent_id = parent.id

    with session_factory() as db:
        with pytest.raises(DomainError) as error:
            knowledge_review.delete_point(db, parent_id, cascade=False)
        assert error.value.code == "knowledge_point_has_children"

    with session_factory() as db:
        document = db.get(Document, document_id)
        document.status = "parsing"
        db.commit()
    recover_interrupted_tasks(session_factory)
    with session_factory() as db:
        assert db.get(Document, document_id).status == "failed"
