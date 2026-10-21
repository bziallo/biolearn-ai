from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import PracticeStatus, QuestionStatus, QuestionType
from app.core.authz import (
    current_principal,
    ensure_practice_session_access,
    ensure_subject_access,
)
from app.core.errors import DomainError
from app.db.base import utc_now
from app.models import (
    Chapter,
    PracticeAnswer,
    PracticeSession,
    Question,
    Subject,
)
from app.schemas.question import (
    ManualGradeRequest,
    PracticeAnswerResult,
    PracticeQuestion,
    PracticeResult,
    PracticeSessionRead,
    PracticeStartRequest,
    PracticeSubmitRequest,
    QuestionRead,
    WrongQuestionRead,
)
from app.services import questions


def _subject(db: Session, subject_id: str) -> Subject:
    return ensure_subject_access(db, subject_id)


def _chapter(db: Session, chapter_id: str | None, subject_id: str) -> Chapter | None:
    if not chapter_id:
        return None
    chapter = db.get(Chapter, chapter_id)
    if chapter is None or chapter.subject_id != subject_id:
        raise DomainError(422, "chapter_subject_mismatch", "章节不属于所选学科")
    return chapter


def _practice_questions(db: Session, question_ids: list[str]) -> list[Question]:
    if not question_ids:
        return []
    rows = db.scalars(
        select(Question)
        .options(
            selectinload(Question.knowledge_points),
            selectinload(Question.subject),
            selectinload(Question.chapter),
            selectinload(Question.source_document),
        )
        .where(Question.id.in_(question_ids))
    ).all()
    by_id = {question.id: question for question in rows}
    return [by_id[item] for item in question_ids if item in by_id]


def _public_question(question: Question) -> PracticeQuestion:
    read = questions.question_read(question)
    return PracticeQuestion(
        id=read.id,
        type=read.type,
        stem=read.stem,
        options=read.options,
        difficulty=read.difficulty,
        chapter_id=read.chapter_id,
        knowledge_points=read.knowledge_points,
    )


def _session_read(db: Session, session: PracticeSession, *, with_questions: bool) -> PracticeSessionRead:
    subject = db.get(Subject, session.subject_id)
    chapter = db.get(Chapter, session.chapter_id) if session.chapter_id else None
    question_list = _practice_questions(db, session.question_ids) if with_questions else []
    return PracticeSessionRead(
        id=session.id,
        subject_id=session.subject_id,
        subject_name=subject.name if subject else "",
        chapter_id=session.chapter_id,
        chapter_name=chapter.name if chapter else None,
        status=session.status,
        total_questions=session.total_questions,
        answered_count=session.answered_count,
        correct_count=session.correct_count,
        pending_manual_count=session.pending_manual_count,
        score=session.score,
        started_at=session.started_at,
        finished_at=session.finished_at,
        questions=[_public_question(question) for question in question_list],
    )


def get_session_or_404(db: Session, session_id: str) -> PracticeSession:
    session = db.get(PracticeSession, session_id)
    if session is None:
        raise DomainError(404, "practice_session_not_found", "练习记录不存在")
    ensure_practice_session_access(db, session)
    return session


def start_session(db: Session, payload: PracticeStartRequest) -> PracticeSessionRead:
    principal = current_principal()
    subject = _subject(db, payload.subject_id)
    _chapter(db, payload.chapter_id, payload.subject_id)
    conditions = [
        Question.subject_id == subject.id,
        Question.status == QuestionStatus.APPROVED.value,
    ]
    if payload.chapter_id:
        conditions.append(Question.chapter_id == payload.chapter_id)
    if payload.types:
        conditions.append(Question.type.in_([item.value for item in payload.types]))
    if payload.difficulty:
        conditions.append(Question.difficulty == payload.difficulty.value)
    if payload.knowledge_point_ids:
        # Validate scope and approval before using the filter.
        questions.load_approved_points(
            db,
            payload.subject_id,
            payload.knowledge_point_ids,
            chapter_id=payload.chapter_id,
        )
        conditions.append(
            Question.id.in_(
                select(questions.question_knowledge_points.c.question_id).where(
                    questions.question_knowledge_points.c.knowledge_point_id.in_(
                        payload.knowledge_point_ids
                    )
                )
            )
        )
    if payload.wrong_only:
        wrong_ids = db.scalars(
            select(PracticeAnswer.question_id)
            .join(PracticeSession, PracticeAnswer.session_id == PracticeSession.id)
            .where(
                PracticeSession.subject_id == subject.id,
                PracticeSession.user_id == principal.user_id
                if not principal.legacy
                else True,
                PracticeAnswer.is_correct.is_(False),
                PracticeAnswer.question_id.is_not(None),
            )
            .distinct()
        ).all()
        if not wrong_ids:
            raise DomainError(409, "no_wrong_questions", "当前范围还没有错题")
        conditions.append(Question.id.in_(wrong_ids))

    available = db.scalar(
        select(func.count(Question.id)).where(*conditions)
    ) or 0
    if available == 0:
        raise DomainError(
            409,
            "no_approved_questions",
            "当前筛选范围没有已通过审核的题目",
        )
    selected = db.scalars(
        select(Question.id)
        .where(*conditions)
        .order_by(func.random())
        .limit(min(max(payload.count, 1), 50))
    ).all()
    session = PracticeSession(
        user_id=principal.user_id if not principal.legacy else None,
        subject_id=subject.id,
        chapter_id=payload.chapter_id,
        status=PracticeStatus.IN_PROGRESS.value,
        filters=payload.model_dump(mode="json"),
        question_ids=list(selected),
        total_questions=len(selected),
        answered_count=0,
        correct_count=0,
        pending_manual_count=0,
        score=None,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_read(db, session, with_questions=True)


def get_session(db: Session, session_id: str) -> PracticeSessionRead:
    session = get_session_or_404(db, session_id)
    return _session_read(db, session, with_questions=True)


def _normalize_choice_answer(value: Any) -> list[str]:
    if isinstance(value, dict):
        raw = value.get("choices", value.get("choice_keys", []))
    else:
        raw = value
    if not isinstance(raw, list):
        return []
    return list(dict.fromkeys(str(item).strip().upper() for item in raw if str(item).strip()))


def _grade_answer(question: Question, user_answer: dict[str, Any]) -> tuple[bool | None, float | None, str | None, str]:
    if question.type in {
        QuestionType.SINGLE_CHOICE.value,
        QuestionType.MULTIPLE_CHOICE.value,
    }:
        correct = set(_normalize_choice_answer(question.answer))
        given = set(_normalize_choice_answer(user_answer))
        is_correct = bool(given) and given == correct
        feedback = "回答正确" if is_correct else "答案不正确"
        return is_correct, 1.0 if is_correct else 0.0, feedback, "auto"

    if question.type == QuestionType.TRUE_FALSE.value:
        expected = question.answer.get("boolean")
        value = user_answer.get("boolean", user_answer.get("value"))
        if isinstance(value, str):
            value = value.strip().lower() in {"true", "1", "正确", "t"}
        is_correct = isinstance(value, bool) and value == expected
        feedback = "回答正确" if is_correct else "答案不正确"
        return is_correct, 1.0 if is_correct else 0.0, feedback, "auto"

    return None, None, "简答题等待人工评分", "pending"


def submit_answers(
    db: Session,
    session_id: str,
    payload: PracticeSubmitRequest,
) -> PracticeResult:
    session = get_session_or_404(db, session_id)
    if session.status != PracticeStatus.IN_PROGRESS.value:
        raise DomainError(409, "practice_session_completed", "该练习已提交，不能重复作答")
    expected_ids = list(session.question_ids)
    answer_map: dict[str, dict[str, Any]] = {}
    for item in payload.answers:
        if item.question_id in answer_map:
            raise DomainError(422, "duplicate_answer", "同一道题不能提交多次")
        answer_map[item.question_id] = item.user_answer
    if set(answer_map) != set(expected_ids):
        raise DomainError(
            422,
            "practice_answers_incomplete",
            "请为本次练习的每道题提交答案",
        )
    question_list = _practice_questions(db, expected_ids)
    if len(question_list) != len(expected_ids):
        raise DomainError(409, "question_changed", "部分题目已被删除，请重新开始练习")

    correct = 0
    pending = 0
    for question in question_list:
        user_answer = answer_map[question.id]
        is_correct, score, feedback, graded_by = _grade_answer(question, user_answer)
        if is_correct is True:
            correct += 1
        if graded_by == "pending":
            pending += 1
        snapshot = questions.question_read(question).model_dump(mode="json")
        db.add(
            PracticeAnswer(
                session_id=session.id,
                question_id=question.id,
                question_snapshot=snapshot,
                user_answer=user_answer,
                is_correct=is_correct,
                score=score,
                max_score=1.0,
                feedback=feedback,
                graded_by=graded_by,
            )
        )
    session.answered_count = len(question_list)
    session.correct_count = correct
    session.pending_manual_count = pending
    session.score = None if pending else round(correct / len(question_list) * 100, 1)
    session.status = PracticeStatus.COMPLETED.value
    session.finished_at = utc_now()
    db.commit()
    return get_result(db, session.id)


def _answer_result(answer: PracticeAnswer, question: Question | None) -> PracticeAnswerResult:
    if question is None:
        raise DomainError(409, "question_changed", "题目已被删除，无法展示结果")
    return PracticeAnswerResult(
        id=answer.id,
        question=questions.question_read(question),
        user_answer=answer.user_answer,
        is_correct=answer.is_correct,
        score=answer.score,
        max_score=answer.max_score,
        feedback=answer.feedback,
        graded_by=answer.graded_by,
        answered_at=answer.answered_at,
    )


def get_result(db: Session, session_id: str) -> PracticeResult:
    session = get_session_or_404(db, session_id)
    answers = db.scalars(
        select(PracticeAnswer)
        .where(PracticeAnswer.session_id == session.id)
        .order_by(PracticeAnswer.created_at)
    ).all()
    question_ids = [answer.question_id for answer in answers if answer.question_id]
    question_list = _practice_questions(db, question_ids)
    by_id = {question.id: question for question in question_list}
    return PracticeResult(
        session=_session_read(db, session, with_questions=True),
        answers=[
            _answer_result(answer, by_id.get(answer.question_id))
            for answer in answers
        ],
    )


def manual_grade(
    db: Session,
    answer_id: str,
    payload: ManualGradeRequest,
) -> PracticeResult:
    answer = db.get(PracticeAnswer, answer_id)
    if answer is None:
        raise DomainError(404, "practice_answer_not_found", "答题记录不存在")
    session = get_session_or_404(db, answer.session_id)
    if answer.graded_by != "pending":
        raise DomainError(409, "practice_answer_already_graded", "该答案已经评分")
    question = db.get(Question, answer.question_id) if answer.question_id else None
    if question is None or question.type != QuestionType.SHORT_ANSWER.value:
        raise DomainError(409, "practice_answer_not_manual", "只有简答题支持人工评分")
    answer.score = payload.score
    answer.is_correct = payload.score >= 0.6
    answer.feedback = payload.feedback or "人工评分"
    answer.graded_by = "manual"
    db.flush()
    pending = db.scalar(
        select(func.count(PracticeAnswer.id)).where(
            PracticeAnswer.session_id == session.id,
            PracticeAnswer.graded_by == "pending",
        )
    ) or 0
    session.pending_manual_count = pending
    session.correct_count = db.scalar(
        select(func.count(PracticeAnswer.id)).where(
            PracticeAnswer.session_id == session.id,
            PracticeAnswer.is_correct.is_(True),
        )
    ) or 0
    if pending == 0:
        total = max(1, session.total_questions)
        session.score = round(session.correct_count / total * 100, 1)
    db.commit()
    return get_result(db, session.id)


def wrong_questions(
    db: Session,
    *,
    subject_id: str,
    chapter_id: str | None = None,
    limit: int = 100,
) -> list[WrongQuestionRead]:
    principal = current_principal()
    _subject(db, subject_id)
    _chapter(db, chapter_id, subject_id)
    answers = db.scalars(
        select(PracticeAnswer)
        .join(PracticeSession, PracticeAnswer.session_id == PracticeSession.id)
        .where(
            PracticeSession.subject_id == subject_id,
            PracticeSession.user_id == principal.user_id
            if not principal.legacy
            else True,
            PracticeAnswer.is_correct.is_(False),
            PracticeAnswer.question_id.is_not(None),
        )
        .order_by(PracticeAnswer.answered_at.desc())
    ).all()
    grouped: dict[str, list[PracticeAnswer]] = {}
    for answer in answers:
        grouped.setdefault(answer.question_id or "", []).append(answer)
    question_list = _practice_questions(db, list(grouped))
    by_id = {question.id: question for question in question_list}
    result: list[WrongQuestionRead] = []
    for question_id, rows in grouped.items():
        question = by_id.get(question_id)
        if question is None or question.status != QuestionStatus.APPROVED.value:
            continue
        if chapter_id and question.chapter_id != chapter_id:
            continue
        latest = rows[0]
        result.append(
            WrongQuestionRead(
                question=questions.question_read(question),
                wrong_count=len(rows),
                last_answer=latest.user_answer,
                last_answered_at=latest.answered_at,
            )
        )
    result.sort(key=lambda item: (-item.wrong_count, str(item.last_answered_at)))
    return result[: max(1, min(limit, 200))]


def list_sessions(
    db: Session,
    *,
    subject_id: str | None = None,
    limit: int = 20,
) -> list[PracticeSessionRead]:
    statement = select(PracticeSession).order_by(
        PracticeSession.started_at.desc()
    )
    principal = current_principal()
    if not principal.legacy:
        statement = statement.where(PracticeSession.user_id == principal.user_id)
    if subject_id:
        statement = statement.where(PracticeSession.subject_id == subject_id)
    sessions = db.scalars(statement.limit(max(1, min(limit, 100)))).all()
    return [_session_read(db, session, with_questions=False) for session in sessions]
