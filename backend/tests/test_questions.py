from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import QuestionStatus, QuestionType
from app.core.errors import DomainError
from app.db.base import utc_now
from app.models import Chapter, Document, KnowledgePoint, Question, Subject
from app.schemas.question import (
    ManualGradeRequest,
    PracticeAnswerInput,
    PracticeStartRequest,
    PracticeSubmitRequest,
    QuestionCreate,
    QuestionGenerateRequest,
    QuestionUpdate,
)
from app.services import practice as practice_service
from app.services import question_generation
from app.services import questions as question_service
from app.services.ai_client import (
    AIClientCancelled,
    AIClientError,
    _error_kind,
    _safe_provider_error,
    extract_json_object,
)


class FakeAI:
    def __init__(self, responses: list[dict | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[str] = []

    def chat_json(self, system_prompt: str, user_prompt: str, *, cancel_check=None):
        self.calls.append(user_prompt)
        if cancel_check is not None and cancel_check():
            raise AIClientCancelled()
        if not self.responses:
            raise AIClientError("fake AI 没有更多响应")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def make_context(session_factory) -> dict[str, Any]:
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
            name="蛋白质讲义",
            content_title="蛋白质",
            original_filename="protein.txt",
            storage_name="protein.txt",
            mime_type="text/plain",
            extension=".txt",
            size_bytes=10,
            sha256="d" * 64,
            status="parsed",
            page_count=1,
            parsed_at=utc_now(),
        )
        db.add(document)
        db.flush()
        approved = KnowledgePoint(
            subject_id=subject.id,
            chapter_id=chapter.id,
            document_id=document.id,
            name="蛋白质一级结构",
            explanation="氨基酸的线性排列顺序。",
            core_points=["氨基酸序列", "肽键"],
            source_quote="一级结构是氨基酸的排列顺序。",
            source_quote_verified=True,
            source_page=5,
            source_slide=2,
            source_locator="第 5 页",
            review_status="approved",
            needs_review=False,
            origin="ai",
            published_at=utc_now(),
        )
        approved2 = KnowledgePoint(
            subject_id=subject.id,
            chapter_id=chapter.id,
            document_id=document.id,
            name="蛋白质变性",
            explanation="空间结构被破坏，生物活性丧失。",
            core_points=["空间结构"],
            source_page=6,
            source_slide=3,
            source_locator="第 6 页",
            review_status="approved",
            needs_review=False,
            origin="ai",
            published_at=utc_now(),
        )
        pending = KnowledgePoint(
            subject_id=subject.id,
            chapter_id=chapter.id,
            document_id=document.id,
            name="未审核概念",
            explanation="尚未审核。",
            core_points=[],
            review_status="pending",
            needs_review=True,
            origin="ai",
        )
        db.add_all([approved, approved2, pending])
        db.commit()
        return {
            "subject_id": subject.id,
            "chapter_id": chapter.id,
            "document_id": document.id,
            "approved_ids": [approved.id, approved2.id],
            "pending_id": pending.id,
        }


def single_payload(kp_ids: list[str], subject_id: str, chapter_id: str) -> dict:
    return {
        "subject_id": subject_id,
        "chapter_id": chapter_id,
        "knowledge_point_ids": kp_ids,
        "type": "single_choice",
        "stem": "蛋白质一级结构指的是什么？",
        "options": [
            {"key": "A", "text": "氨基酸的线性排列顺序"},
            {"key": "B", "text": "局部折叠"},
            {"key": "C", "text": "空间构象"},
        ],
        "answer": {"choices": ["A"]},
        "explanation": "一级结构是氨基酸的线性排列顺序。",
        "difficulty": "easy",
    }


def create_approved_question(
    db,
    context: dict,
    *,
    stem: str = "蛋白质一级结构指的是什么？",
    question_type: str = "single_choice",
    options: list[dict] | None = None,
    answer: dict | None = None,
    explanation: str = "一级结构是氨基酸的线性排列顺序。",
    kp_ids: list[str] | None = None,
):
    payload = single_payload(kp_ids or context["approved_ids"], context["subject_id"], context["chapter_id"])
    payload.update(
        {
            "stem": stem,
            "type": question_type,
            "options": options if options is not None else payload["options"],
            "answer": answer if answer is not None else payload["answer"],
            "explanation": explanation,
        }
    )
    question = question_service.create_question(db, QuestionCreate(**payload))
    return question_service.review_question(
        db,
        question.id,
        QuestionStatus.APPROVED,
    )


def generated_single(stem: str, kp_id: str) -> dict:
    return {
        "type": "single_choice",
        "stem": stem,
        "options": [
            {"key": "A", "text": "氨基酸序列"},
            {"key": "B", "text": "空间结构"},
        ],
        "answer": {"choices": ["A"]},
        "explanation": "一级结构由氨基酸序列构成。",
        "difficulty": "easy",
        "knowledge_point_ids": [kp_id],
        "confidence": 0.9,
    }


def test_question_manual_validation_review_and_edit_resets_status(
    client: TestClient,
    session_factory,
) -> None:
    context = make_context(session_factory)
    response = client.post(
        "/api/v1/questions",
        json=single_payload(
            context["approved_ids"],
            context["subject_id"],
            context["chapter_id"],
        ),
    )
    assert response.status_code == 201, response.text
    question = response.json()
    assert question["status"] == "pending"
    assert question["origin"] == "manual"
    assert question["knowledge_points"][0]["source_page"] == 5

    duplicate = client.post(
        "/api/v1/questions",
        json=single_payload(
            context["approved_ids"],
            context["subject_id"],
            context["chapter_id"],
        ),
    )
    assert duplicate.status_code == 201, duplicate.text
    assert duplicate.json()["duplicate_of_id"] == question["id"]

    by_point = client.get(
        "/api/v1/questions",
        params={"knowledge_point_id": context["approved_ids"][0]},
    )
    assert by_point.status_code == 200
    assert by_point.json()["total"] == 2

    invalid = single_payload(
        context["approved_ids"],
        context["subject_id"],
        context["chapter_id"],
    )
    invalid["answer"] = {"choices": ["Z"]}
    response = client.post("/api/v1/questions", json=invalid)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "question_invalid"

    approved = client.post(
        f"/api/v1/questions/{question['id']}/review",
        json={"status": "approved"},
    )
    assert approved.status_code == 200
    assert approved.json()["published_at"]

    edited = client.patch(
        f"/api/v1/questions/{question['id']}",
        json={"stem": "蛋白质一级结构的定义是什么？"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["status"] == "pending"
    assert edited.json()["published_at"] is None

    pending = client.post(
        "/api/v1/questions",
        json=single_payload(
            [context["pending_id"]],
            context["subject_id"],
            context["chapter_id"],
        ),
    )
    assert pending.status_code == 409
    assert pending.json()["detail"]["code"] == "knowledge_not_approved"

    bulk = client.post(
        "/api/v1/questions/bulk-review",
        json={
            "ids": [question["id"], duplicate.json()["id"]],
            "status": "rejected",
        },
    )
    assert bulk.status_code == 200, bulk.text
    assert bulk.json()["updated"] == 2
    rejected = client.get(
        "/api/v1/questions",
        params={"subject_id": context["subject_id"], "status": "rejected"},
    )
    assert rejected.json()["total"] == 2


def test_ai_generation_uses_approved_points_and_skips_duplicates(
    session_factory,
    app_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = make_context(session_factory)
    monkeypatch.setattr(
        question_generation,
        "effective_ai_settings",
        lambda _settings=None: app_settings,
    )
    fake = FakeAI(
        [
            {
                "questions": [
                    generated_single(
                        "蛋白质一级结构由什么决定？",
                        context["approved_ids"][0],
                    ),
                    generated_single(
                        "蛋白质一级结构由什么决定？",
                        context["approved_ids"][0],
                    ),
                ]
            }
        ]
    )
    with session_factory() as db:
        job = question_generation.create_generation_job(
            db,
            subject_id=context["subject_id"],
            chapter_id=context["chapter_id"],
            knowledge_point_ids=context["approved_ids"],
            types=[QuestionType.SINGLE_CHOICE],
            count=1,
            difficulty=None,
            settings=app_settings,
        )
    question_generation.run_generation(
        job.id,
        session_factory=session_factory,
        client=fake,
        settings=app_settings,
    )
    with session_factory() as db:
        stored = question_generation.get_job_or_404(db, job.id)
        assert stored.status == "completed"
        assert stored.generated_count == 1
        assert stored.skipped_count == 1
        question = db.query(Question).one()
        assert question.status == "pending"
        assert question.origin == "ai"
        assert [point.id for point in question.knowledge_points] == [
            context["approved_ids"][0]
        ]


def test_generation_rejects_pending_knowledge_and_failure_retry(
    session_factory,
    app_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = make_context(session_factory)
    monkeypatch.setattr(
        question_generation,
        "effective_ai_settings",
        lambda _settings=None: app_settings,
    )
    with session_factory() as db:
        with pytest.raises(DomainError) as error:
            question_generation.create_generation_job(
                db,
                subject_id=context["subject_id"],
                chapter_id=context["chapter_id"],
                knowledge_point_ids=[context["pending_id"]],
                types=[QuestionType.SINGLE_CHOICE],
                count=1,
                settings=app_settings,
            )
        assert error.value.code == "knowledge_not_approved"

        job = question_generation.create_generation_job(
            db,
            subject_id=context["subject_id"],
            chapter_id=context["chapter_id"],
            knowledge_point_ids=context["approved_ids"],
            types=[QuestionType.SINGLE_CHOICE],
            count=1,
            settings=app_settings,
        )
    question_generation.run_generation(
        job.id,
        session_factory=session_factory,
        client=FakeAI([AIClientError("模型超时")]),
        settings=app_settings,
    )
    with session_factory() as db:
        assert question_generation.get_job_or_404(db, job.id).status == "failed"
        assert "模型超时" in (question_generation.get_job_or_404(db, job.id).error or "")
        assert db.query(Question).count() == 0

    with session_factory() as db:
        retry = question_generation.retry_generation_job(
            db,
            job.id,
            settings=app_settings,
        )
    question_generation.run_generation(
        retry.id,
        session_factory=session_factory,
        client=FakeAI(
            [{"questions": [generated_single("蛋白质一级结构由什么决定？", context["approved_ids"][0])]}]
        ),
        settings=app_settings,
    )
    with session_factory() as db:
        assert question_generation.get_job_or_404(db, retry.id).status == "completed"
        assert db.query(Question).count() == 1


def test_generation_cancel_and_duplicate_question_warning(
    session_factory,
    app_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = make_context(session_factory)
    monkeypatch.setattr(
        question_generation,
        "effective_ai_settings",
        lambda _settings=None: app_settings,
    )
    with session_factory() as db:
        job = question_generation.create_generation_job(
            db,
            subject_id=context["subject_id"],
            chapter_id=context["chapter_id"],
            knowledge_point_ids=context["approved_ids"],
            types=[QuestionType.SINGLE_CHOICE],
            count=2,
            settings=app_settings,
        )
        question_generation.cancel_generation_job(db, job.id)
    question_generation.run_generation(
        job.id,
        session_factory=session_factory,
        client=FakeAI([]),
        settings=app_settings,
    )
    with session_factory() as db:
        stored = question_generation.get_job_or_404(db, job.id)
        assert stored.status == "cancelled"
        assert db.query(Question).count() == 0


def test_question_and_practice_api_filters_and_persistence(
    client: TestClient,
    session_factory,
    app_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = make_context(session_factory)
    with session_factory() as db:
        single = create_approved_question(db, context, stem="蛋白质一级结构由什么决定？")
        short = create_approved_question(
            db,
            context,
            stem="简述蛋白质一级结构的定义。",
            question_type="short_answer",
            options=[],
            answer={"text": "氨基酸的线性排列顺序。"},
            explanation="一级结构是线性序列。",
        )

    listed = client.get(
        "/api/v1/questions",
        params={
            "subject_id": context["subject_id"],
            "status": "approved",
            "q": "一级结构",
        },
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 2
    assert listed.json()["stats"]["approved"] == 2

    started = client.post(
        "/api/v1/practice/sessions",
        json={
            "subject_id": context["subject_id"],
            "count": 2,
            "types": ["single_choice", "short_answer"],
        },
    )
    assert started.status_code == 200, started.text
    session = started.json()
    assert len(session["questions"]) == 2
    submitted = client.post(
        f"/api/v1/practice/sessions/{session['id']}/submit",
        json={
            "answers": [
                {"question_id": single.id, "user_answer": {"choices": ["A"]}},
                {"question_id": short.id, "user_answer": {"text": "氨基酸序列"}},
            ]
        },
    )
    assert submitted.status_code == 200, submitted.text
    result = submitted.json()
    assert result["session"]["pending_manual_count"] == 1
    duplicate = client.post(
        f"/api/v1/practice/sessions/{session['id']}/submit",
        json={
            "answers": [
                {"question_id": single.id, "user_answer": {"choices": ["A"]}},
                {"question_id": short.id, "user_answer": {"text": "氨基酸序列"}},
            ]
        },
    )
    assert duplicate.status_code == 409

    pending_answer = next(
        answer
        for answer in result["answers"]
        if answer["graded_by"] == "pending"
    )
    graded = client.post(
        f"/api/v1/practice/answers/{pending_answer['id']}/grade",
        json={"score": 0.8, "feedback": "人工确认"},
    )
    assert graded.status_code == 200, graded.text
    assert graded.json()["session"]["score"] == 100

    # A fresh session on a fresh SQLAlchemy session proves the records are
    # persisted rather than held in process memory.
    with session_factory() as db:
        from app.models import PracticeSession

        assert db.query(PracticeSession).count() == 1
        assert db.get(PracticeSession, session["id"]).status == "completed"

    monkeypatch.setattr(
        question_generation,
        "run_generation",
        lambda job_id: None,
    )
    monkeypatch.setattr(
        question_generation,
        "effective_ai_settings",
        lambda _settings=None: app_settings,
    )
    generated = client.post(
        "/api/v1/questions/generate",
        json={
            "subject_id": context["subject_id"],
            "knowledge_point_ids": context["approved_ids"],
            "types": ["single_choice"],
            "count": 1,
        },
    )
    assert generated.status_code == 200, generated.text
    job_id = generated.json()["id"]
    job = client.get(f"/api/v1/questions/generation-jobs/{job_id}")
    assert job.status_code == 200
    cancelled = client.post(f"/api/v1/questions/generation-jobs/{job_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_generation_rejects_inconsistent_ai_output(
    session_factory,
    app_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = make_context(session_factory)
    monkeypatch.setattr(
        question_generation,
        "effective_ai_settings",
        lambda _settings=None: app_settings,
    )
    with session_factory() as db:
        job = question_generation.create_generation_job(
            db,
            subject_id=context["subject_id"],
            knowledge_point_ids=context["approved_ids"],
            types=[QuestionType.SINGLE_CHOICE],
            count=1,
            settings=app_settings,
        )
    question_generation.run_generation(
        job.id,
        session_factory=session_factory,
        client=FakeAI(
            [
                {
                    "questions": [
                        {
                            **generated_single(
                                "蛋白质一级结构由什么决定？",
                                context["approved_ids"][0],
                            ),
                            "answer": {"choices": ["A", "B"]},
                        }
                    ]
                }
            ]
        ),
        settings=app_settings,
    )
    with session_factory() as db:
        stored = question_generation.get_job_or_404(db, job.id)
        assert stored.status == "failed"
        assert "单选题" in (stored.error or "")
        assert db.query(Question).count() == 0


def test_practice_grading_wrong_questions_and_manual_short_answer(
    session_factory,
) -> None:
    context = make_context(session_factory)
    with session_factory() as db:
        single = create_approved_question(
            db,
            context,
            stem="蛋白质一级结构由什么决定？",
        )
        multiple = create_approved_question(
            db,
            context,
            stem="蛋白质结构层次包括哪些？",
            question_type="multiple_choice",
            options=[
                {"key": "A", "text": "一级结构"},
                {"key": "B", "text": "二级结构"},
                {"key": "C", "text": "错误选项"},
            ],
            answer={"choices": ["A", "B"]},
            explanation="一级和二级结构都是结构层次。",
        )
        judgment = create_approved_question(
            db,
            context,
            stem="蛋白质变性会破坏空间结构。",
            question_type="true_false",
            options=[],
            answer={"boolean": True},
            explanation="变性会破坏空间结构。",
        )
        short = create_approved_question(
            db,
            context,
            stem="简述蛋白质一级结构与功能的关系。",
            question_type="short_answer",
            options=[],
            answer={"text": "一级结构决定高级结构和功能。"},
            explanation="一级结构是结构基础。",
        )

    with session_factory() as db:
        session = practice_service.start_session(
            db,
            PracticeStartRequest(
                subject_id=context["subject_id"],
                chapter_id=context["chapter_id"],
                count=4,
                types=[
                    QuestionType.SINGLE_CHOICE,
                    QuestionType.MULTIPLE_CHOICE,
                    QuestionType.TRUE_FALSE,
                    QuestionType.SHORT_ANSWER,
                ],
            ),
        )
        assert len(session.questions) == 4
        question_ids = {question.id for question in session.questions}
        result = practice_service.submit_answers(
            db,
            session.id,
            PracticeSubmitRequest(
                answers=[
                    PracticeAnswerInput(question_id=single.id, user_answer={"choices": ["A"]}),
                    PracticeAnswerInput(
                        question_id=multiple.id,
                        user_answer={"choices": ["B", "A", "A"]},
                    ),
                    PracticeAnswerInput(
                        question_id=judgment.id,
                        user_answer={"boolean": True},
                    ),
                    PracticeAnswerInput(
                        question_id=short.id,
                        user_answer={"text": "一级结构决定功能"},
                    ),
                ]
            ),
        )
        assert {answer.question.id for answer in result.answers} == question_ids
        assert result.session.pending_manual_count == 1
        assert result.session.score is None
        short_answer = next(
            answer for answer in result.answers if answer.question.type == "short_answer"
        )
        assert short_answer.graded_by == "pending"

        graded = practice_service.manual_grade(
            db,
            short_answer.id,
            ManualGradeRequest(score=1.0, feedback="要点正确"),
        )
        assert graded.session.pending_manual_count == 0
        assert graded.session.score == 100
        assert graded.session.correct_count == 4

    with session_factory() as db:
        wrong_session = practice_service.start_session(
            db,
            PracticeStartRequest(
                subject_id=context["subject_id"],
                types=[QuestionType.SINGLE_CHOICE],
                count=1,
            ),
        )
        practice_service.submit_answers(
            db,
            wrong_session.id,
            PracticeSubmitRequest(
                answers=[
                    PracticeAnswerInput(question_id=single.id, user_answer={"choices": ["B"]})
                ]
            ),
        )
        wrong = practice_service.wrong_questions(
            db,
            subject_id=context["subject_id"],
        )
        assert len(wrong) == 1
        assert wrong[0].question.id == single.id
        retry = practice_service.start_session(
            db,
            PracticeStartRequest(
                subject_id=context["subject_id"],
                wrong_only=True,
                count=5,
            ),
        )
        assert retry.questions
        assert retry.questions[0].id == single.id


def test_generation_normalizes_scalar_true_false_answer(
    session_factory,
    app_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real model returns ``"answer": true`` for true/false questions."""

    context = make_context(session_factory)
    monkeypatch.setattr(
        question_generation,
        "effective_ai_settings",
        lambda _settings=None: app_settings,
    )
    with session_factory() as db:
        job = question_generation.create_generation_job(
            db,
            subject_id=context["subject_id"],
            knowledge_point_ids=context["approved_ids"],
            types=[QuestionType.TRUE_FALSE],
            count=1,
            settings=app_settings,
        )
    fake = FakeAI(
        [
            {
                "questions": [
                    {
                        "type": "true_false",
                        "stem": "蛋白质变性后生物活性丧失。",
                        "options": [],
                        # Scalar, not {"boolean": ...}: this is what DeepSeek
                        # actually returned and what used to fail validation.
                        "answer": True,
                        "explanation": "变性破坏空间结构，导致生物活性丧失。",
                        "difficulty": "简单",
                        "knowledge_point_ids": [context["approved_ids"][0]],
                    }
                ]
            }
        ]
    )
    question_generation.run_generation(
        job.id,
        session_factory=session_factory,
        client=fake,
        settings=app_settings,
    )
    with session_factory() as db:
        stored = question_generation.get_job_or_404(db, job.id)
        assert stored.status == "completed", stored.error
        question = db.query(Question).one()
        assert question.type == "true_false"
        assert question.answer == {"boolean": True}
        assert [item["key"] for item in question.options] == ["T", "F"]
        assert question.difficulty == "easy"


def test_generation_repairs_invalid_shape_once(
    session_factory,
    app_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = make_context(session_factory)
    monkeypatch.setattr(
        question_generation,
        "effective_ai_settings",
        lambda _settings=None: app_settings,
    )
    with session_factory() as db:
        job = question_generation.create_generation_job(
            db,
            subject_id=context["subject_id"],
            knowledge_point_ids=context["approved_ids"],
            types=[QuestionType.SINGLE_CHOICE],
            count=1,
            settings=app_settings,
        )
    fake = FakeAI(
        [
            {"questions": [{"type": "single_choice", "stem": "缺少字段的题目"}]},
            {
                "questions": [
                    generated_single(
                        "蛋白质一级结构由什么决定？",
                        context["approved_ids"][0],
                    )
                ]
            },
        ]
    )
    question_generation.run_generation(
        job.id,
        session_factory=session_factory,
        client=fake,
        settings=app_settings,
    )
    with session_factory() as db:
        stored = question_generation.get_job_or_404(db, job.id)
        assert stored.status == "completed", stored.error
        assert stored.timings["format_repairs"] == 1
        assert db.query(Question).count() == 1
    assert len(fake.calls) == 2


def test_generation_fails_after_one_repair_with_field_detail(
    session_factory,
    app_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = make_context(session_factory)
    monkeypatch.setattr(
        question_generation,
        "effective_ai_settings",
        lambda _settings=None: app_settings,
    )
    with session_factory() as db:
        job = question_generation.create_generation_job(
            db,
            subject_id=context["subject_id"],
            knowledge_point_ids=context["approved_ids"],
            types=[QuestionType.SINGLE_CHOICE],
            count=1,
            settings=app_settings,
        )
    invalid = {"questions": [{"type": "single_choice", "stem": "缺少字段的题目"}]}
    fake = FakeAI([invalid, invalid])
    question_generation.run_generation(
        job.id,
        session_factory=session_factory,
        client=fake,
        settings=app_settings,
    )
    with session_factory() as db:
        stored = question_generation.get_job_or_404(db, job.id)
        assert stored.status == "failed"
        assert "字段校验" in (stored.error or "")
        assert stored.generated_count == 0
        assert db.query(Question).count() == 0
        assert stored.timings["format_repairs"] == 1
        assert stored.timings["error_kind"] == "bad_shape"
    # The repair budget is bounded: exactly one extra call, never a loop.
    assert len(fake.calls) == 2


def test_generation_skips_one_invalid_draft_and_keeps_valid(
    session_factory,
    app_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = make_context(session_factory)
    monkeypatch.setattr(
        question_generation,
        "effective_ai_settings",
        lambda _settings=None: app_settings,
    )
    with session_factory() as db:
        job = question_generation.create_generation_job(
            db,
            subject_id=context["subject_id"],
            knowledge_point_ids=context["approved_ids"],
            types=[QuestionType.SINGLE_CHOICE],
            count=1,
            settings=app_settings,
        )
    fake = FakeAI(
        [
            {
                "questions": [
                    generated_single(
                        "蛋白质一级结构由什么决定？",
                        context["approved_ids"][0],
                    ),
                    {
                        "type": "multiple_choice",
                        "stem": "未请求的题型应当被跳过。",
                        "options": [
                            {"key": "A", "text": "甲"},
                            {"key": "B", "text": "乙"},
                        ],
                        "answer": {"choices": ["A"]},
                        "explanation": "这是一道未请求的多选题。",
                        "difficulty": "medium",
                        "knowledge_point_ids": [context["approved_ids"][0]],
                    },
                ]
            }
        ]
    )
    question_generation.run_generation(
        job.id,
        session_factory=session_factory,
        client=fake,
        settings=app_settings,
    )
    with session_factory() as db:
        stored = question_generation.get_job_or_404(db, job.id)
        assert stored.status == "completed", stored.error
        assert stored.generated_count == 1
        assert stored.skipped_count == 1
        assert any("未请求的题型" in item for item in stored.timings["warnings"])
        assert db.query(Question).count() == 1


def test_generation_reports_timeout_category_without_leaking_detail(
    session_factory,
    app_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = make_context(session_factory)
    monkeypatch.setattr(
        question_generation,
        "effective_ai_settings",
        lambda _settings=None: app_settings,
    )
    with session_factory() as db:
        job = question_generation.create_generation_job(
            db,
            subject_id=context["subject_id"],
            knowledge_point_ids=context["approved_ids"],
            types=[QuestionType.SINGLE_CHOICE],
            count=1,
            settings=app_settings,
        )
    question_generation.run_generation(
        job.id,
        session_factory=session_factory,
        client=FakeAI(
            [
                AIClientError(
                    "AI 请求超时（超过 1 秒），请稍后重试",
                    kind="timeout",
                )
            ]
        ),
        settings=app_settings,
    )
    with session_factory() as db:
        stored = question_generation.get_job_or_404(db, job.id)
        assert stored.status == "failed"
        assert "超时" in (stored.error or "")
        assert stored.timings["error_kind"] == "timeout"
        assert db.query(Question).count() == 0


def test_extract_json_object_handles_fences_and_prose() -> None:
    assert extract_json_object('```json\n{"questions": []}\n```') == {
        "questions": []
    }
    assert extract_json_object(
        '下面是结果：\n{"questions": [{"stem": "题干"}]}\n以上。'
    ) == {"questions": [{"stem": "题干"}]}
    assert extract_json_object('{"a": {"b": 2}} trailing') == {"a": {"b": 2}}
    with pytest.raises(ValueError):
        extract_json_object("这不是 JSON")


def test_provider_errors_are_classified_distinctly() -> None:
    def response(status: int, payload: dict[str, Any]) -> httpx.Response:
        return httpx.Response(status, json=payload)

    assert "余额" in _safe_provider_error(
        response(402, {"error": {"code": "insufficient_quota"}})
    )
    assert "速率限制" in _safe_provider_error(
        response(429, {"error": {"code": "rate_limit_exceeded"}})
    )
    assert "认证失败" in _safe_provider_error(
        response(401, {"error": {"code": "invalid_api_key"}})
    )
    assert "暂时不可用" in _safe_provider_error(response(503, {}))
    assert "上下文" in _safe_provider_error(
        response(400, {"error": {"code": "context_length_exceeded"}})
    )
    assert _error_kind(402) == "quota"
    assert _error_kind(429) == "rate_limit"
    assert _error_kind(503) == "server"
    assert _error_kind(400) == "bad_request"


def test_generation_reports_database_write_failure_distinctly(
    session_factory,
    app_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = make_context(session_factory)
    monkeypatch.setattr(
        question_generation,
        "effective_ai_settings",
        lambda _settings=None: app_settings,
    )
    with session_factory() as db:
        job = question_generation.create_generation_job(
            db,
            subject_id=context["subject_id"],
            knowledge_point_ids=context["approved_ids"],
            types=[QuestionType.SINGLE_CHOICE],
            count=1,
            settings=app_settings,
        )

    original_add = Session.add

    def failing_add(self, instance, *args, **kwargs):
        if instance.__class__.__name__ == "Question":
            raise SQLAlchemyError("simulated write failure")
        return original_add(self, instance, *args, **kwargs)

    monkeypatch.setattr(Session, "add", failing_add)
    question_generation.run_generation(
        job.id,
        session_factory=session_factory,
        client=FakeAI(
            [
                {
                    "questions": [
                        generated_single(
                            "蛋白质一级结构由什么决定？",
                            context["approved_ids"][0],
                        )
                    ]
                }
            ]
        ),
        settings=app_settings,
    )
    with session_factory() as db:
        stored = question_generation.get_job_or_404(db, job.id)
        assert stored.status == "failed"
        assert "保存到数据库失败" in (stored.error or "")
        assert stored.timings["error_kind"] == "database"
        assert db.query(Question).count() == 0
