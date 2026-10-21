from __future__ import annotations

import threading
import time

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.base import utc_now
from app.models import Chapter, Document, DocumentChunk, KnowledgePoint, Subject
from app.services import knowledge as knowledge_service
from app.services.ai_client import AIClientError


ANALYSIS = {
    "theme": "蛋白质的结构与功能",
    "learning_objectives": ["理解一级结构"],
    "sections": ["一级结构", "二级结构"],
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
            "name": "蛋白质知识点",
            "type": "basic_concept",
            "explanation": "来自当前分块的说明。",
            "core_points": ["要点"],
            "conditions": None,
            "source_quote": None,
            "confidence": 0.9,
            "needs_review": False,
            "parent_name": None,
        }
    ]
}

MERGE = {
    "merged_points": [
        {
            "ref": "m1",
            "name": "蛋白质知识点",
            "type": "basic_concept",
            "explanation": "合并后的说明。",
            "core_points": ["要点"],
            "conditions": None,
            "parent_ref": None,
            "source_point_ids": [1, 2, 3],
            "confidence": 0.9,
            "needs_review": False,
            "conflict_note": None,
        }
    ]
}


class PromptFakeAI:
    def __init__(self, *, fail_marker: str | None = None) -> None:
        self.fail_marker = fail_marker
        self.calls: list[str] = []
        self.lock = threading.Lock()

    def chat_json(self, system_prompt: str, user_prompt: str, *, cancel_check=None):
        with self.lock:
            self.calls.append(user_prompt)
        if "请分析整章结构" in user_prompt:
            return ANALYSIS
        if "当前分块" in user_prompt:
            # A small delay makes the test exercise overlapping calls.
            time.sleep(0.03)
            if self.fail_marker and self.fail_marker in user_prompt:
                raise AIClientError("模拟分块提取失败")
            return EXTRACTION
        if "merged_points" in user_prompt:
            return MERGE
        raise AssertionError("unexpected prompt")


def make_multi_chunk_document(
    session_factory: sessionmaker[Session],
    count: int = 3,
) -> str:
    with session_factory() as db:
        subject = Subject(name="生物化学", description="")
        db.add(subject)
        db.flush()
        chapter = Chapter(subject_id=subject.id, name="蛋白质", description="")
        db.add(chapter)
        db.flush()
        document = Document(
            subject_id=subject.id,
            chapter_id=chapter.id,
            name="并发测试资料",
            content_title="蛋白质",
            original_filename="concurrency.txt",
            storage_name="concurrency.txt",
            mime_type="text/plain",
            extension=".txt",
            size_bytes=100,
            sha256="c" * 64,
            status="parsed",
            page_count=count,
            parsed_at=utc_now(),
        )
        db.add(document)
        db.flush()
        for index in range(count):
            content = f"第 {index + 1} 块 CHUNK-{index + 1} 蛋白质内容。"
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=index,
                    heading_path="蛋白质",
                    heading_level=1,
                    content=content,
                    page_start=index + 1,
                    page_end=index + 1,
                    char_start=0,
                    char_end=len(content),
                    block_start=index,
                    block_end=index,
                    location_label=f"第 {index + 1} 页",
                )
            )
        db.commit()
        return document.id


def test_concurrent_extraction_records_timings_and_completes(
    client,
    session_factory,
    app_settings: Settings,
) -> None:
    document_id = make_multi_chunk_document(session_factory, 3)
    job = knowledge_service.create_extraction_job(
        session_factory(),
        document_id,
        settings=app_settings,
    )
    fake = PromptFakeAI()
    knowledge_service.run_extraction(
        job.id,
        session_factory=session_factory,
        client=fake,
        settings=app_settings,
    )

    completed = client.get(f"/api/v1/knowledge-jobs/{job.id}").json()
    assert completed["status"] == "completed"
    assert completed["extracted_count"] == 3
    assert completed["processed_chunks"] == 3
    assert completed["timings"]["concurrency"] == 3
    assert completed["timings"]["analysis_seconds"] >= 0
    assert completed["timings"]["extraction_seconds"] >= 0.03
    assert completed["timings"]["merge_seconds"] >= 0
    assert completed["timings"]["persist_seconds"] >= 0
    assert completed["timings"]["total_seconds"] >= 0
    # 3 chunk calls + 1 analysis; identical points are deduped before merge.
    assert len(fake.calls) == 4

    with session_factory() as db:
        points = (
            db.query(KnowledgePoint)
            .filter(KnowledgePoint.document_id == document_id)
            .all()
        )
        assert len(points) == 1
        assert points[0].name == "蛋白质知识点"


def test_partial_chunk_failure_marks_failed_and_retry_recovers(
    client,
    session_factory,
    app_settings: Settings,
) -> None:
    document_id = make_multi_chunk_document(session_factory, 3)
    job = knowledge_service.create_extraction_job(
        session_factory(),
        document_id,
        settings=app_settings,
    )
    knowledge_service.run_extraction(
        job.id,
        session_factory=session_factory,
        client=PromptFakeAI(fail_marker="CHUNK-2"),
        settings=app_settings,
    )

    failed = client.get(f"/api/v1/knowledge-jobs/{job.id}").json()
    assert failed["status"] == "failed"
    assert "模拟分块提取失败" in failed["error"]
    assert failed["timings"]["extraction_seconds"] >= 0
    with session_factory() as db:
        assert (
            db.query(KnowledgePoint)
            .filter(KnowledgePoint.document_id == document_id)
            .count()
            == 0
        )

    retry = knowledge_service.retry_extraction(
        session_factory(),
        job.id,
        settings=app_settings,
    )
    knowledge_service.run_extraction(
        retry.id,
        session_factory=session_factory,
        client=PromptFakeAI(),
        settings=app_settings,
    )
    completed = client.get(f"/api/v1/knowledge-jobs/{retry.id}").json()
    assert completed["status"] == "completed"
    assert completed["attempts"] == 2
    with session_factory() as db:
        assert (
            db.query(KnowledgePoint)
            .filter(KnowledgePoint.document_id == document_id)
            .count()
            == 1
        )
