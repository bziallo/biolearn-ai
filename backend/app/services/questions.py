from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import (
    KnowledgePointType,
    QuestionDifficulty,
    QuestionOrigin,
    QuestionStatus,
    QuestionType,
)
from app.core.errors import DomainError
from app.db.base import utc_now
from app.models import (
    Chapter,
    KnowledgePoint,
    Question,
    QuestionGenerationJob,
    Subject,
)
from app.models.question import question_knowledge_points
from app.schemas.question import (
    QuestionCreate,
    QuestionKnowledgePointBrief,
    QuestionListResponse,
    QuestionOption,
    QuestionRead,
    QuestionStats,
    QuestionUpdate,
)
from app.services.knowledge_common import normalize_name

DEFAULT_TRUE_FALSE_OPTIONS = [
    {"key": "T", "text": "正确"},
    {"key": "F", "text": "错误"},
]


@dataclass(slots=True)
class ValidatedQuestion:
    type: str
    stem: str
    options: list[dict[str, str]]
    answer: dict[str, Any]
    grading_rule: dict[str, Any]
    explanation: str
    difficulty: str
    knowledge_point_ids: list[str]


def normalize_stem(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _get_subject(db: Session, subject_id: str) -> Subject:
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise DomainError(404, "subject_not_found", "学科不存在")
    return subject


def _get_chapter(
    db: Session,
    chapter_id: str | None,
    subject_id: str,
) -> Chapter | None:
    if not chapter_id:
        return None
    chapter = db.get(Chapter, chapter_id)
    if chapter is None or chapter.subject_id != subject_id:
        raise DomainError(422, "chapter_subject_mismatch", "章节不属于所选学科")
    return chapter


def load_approved_points(
    db: Session,
    subject_id: str,
    point_ids: list[str],
    *,
    chapter_id: str | None = None,
) -> list[KnowledgePoint]:
    _get_subject(db, subject_id)
    _get_chapter(db, chapter_id, subject_id)
    unique_ids = list(dict.fromkeys(point_ids))
    if unique_ids:
        points = db.scalars(
            select(KnowledgePoint).where(KnowledgePoint.id.in_(unique_ids))
        ).all()
        if len(points) != len(unique_ids):
            raise DomainError(
                404,
                "knowledge_point_not_found",
                "部分知识点不存在，请刷新后重试",
            )
        if any(point.subject_id != subject_id for point in points):
            raise DomainError(
                422,
                "knowledge_point_subject_mismatch",
                "知识点不属于所选学科",
            )
        if chapter_id and any(point.chapter_id != chapter_id for point in points):
            raise DomainError(
                422,
                "knowledge_point_chapter_mismatch",
                "知识点不属于所选章节",
            )
        not_approved = [
            point.name
            for point in points
            if point.review_status != "approved"
        ]
        if not_approved:
            raise DomainError(
                409,
                "knowledge_not_approved",
                "只能使用已通过审核的知识点生成题目",
                knowledge_points=not_approved[:10],
            )
        return points

    statement = select(KnowledgePoint).where(
        KnowledgePoint.subject_id == subject_id,
        KnowledgePoint.review_status == "approved",
    )
    if chapter_id:
        statement = statement.where(KnowledgePoint.chapter_id == chapter_id)
    points = db.scalars(
        statement.order_by(KnowledgePoint.created_at, KnowledgePoint.name)
    ).all()
    if not points:
        raise DomainError(
            409,
            "no_approved_knowledge_points",
            "所选范围内没有已通过审核的知识点，不能生成题目",
        )
    return points


def _normalize_options(
    question_type: QuestionType,
    options: list[QuestionOption | dict[str, Any]],
) -> list[dict[str, str]]:
    if question_type == QuestionType.SHORT_ANSWER:
        if options:
            raise DomainError(422, "question_invalid", "简答题不能包含选项")
        return []
    if question_type == QuestionType.TRUE_FALSE and not options:
        return [dict(item) for item in DEFAULT_TRUE_FALSE_OPTIONS]
    if len(options) < 2:
        raise DomainError(422, "question_invalid", "选择题至少需要两个选项")
    if len(options) > 8:
        raise DomainError(422, "question_invalid", "选择题最多支持八个选项")

    normalized: list[dict[str, str]] = []
    keys: set[str] = set()
    texts: set[str] = set()
    for item in options:
        if isinstance(item, QuestionOption):
            key, text = item.key, item.text
        else:
            key, text = str(item.get("key", "")), str(item.get("text", ""))
        key = key.strip().upper()
        text = text.strip()
        if not key or not text:
            raise DomainError(422, "question_invalid", "选项不能为空")
        if key in keys:
            raise DomainError(422, "question_invalid", "选项 key 不能重复")
        normalized_text = normalize_stem(text)
        if normalized_text in texts:
            raise DomainError(422, "question_invalid", "选项内容不能重复")
        keys.add(key)
        texts.add(normalized_text)
        normalized.append({"key": key, "text": text})
    return normalized


def _normalize_answer(
    question_type: QuestionType,
    answer: dict[str, Any],
    options: list[dict[str, str]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if question_type in {QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE}:
        raw = answer.get("choices", answer.get("choice_keys", []))
        if not isinstance(raw, list):
            raise DomainError(422, "question_invalid", "选择题答案必须是选项 key 列表")
        choices = list(
            dict.fromkeys(str(item).strip().upper() for item in raw if str(item).strip())
        )
        option_keys = {item["key"] for item in options}
        if not choices:
            raise DomainError(422, "question_invalid", "选择题缺少正确答案")
        if any(choice not in option_keys for choice in choices):
            raise DomainError(422, "question_invalid", "正确答案引用了不存在的选项")
        if question_type == QuestionType.SINGLE_CHOICE and len(choices) != 1:
            raise DomainError(422, "question_invalid", "单选题必须且只能有一个正确答案")
        return {"choices": choices}, {"mode": "choice_exact", "case_sensitive": False}

    if question_type == QuestionType.TRUE_FALSE:
        value = answer.get("boolean")
        if not isinstance(value, bool):
            raise DomainError(422, "question_invalid", "判断题答案必须是布尔值")
        return {"boolean": value}, {"mode": "boolean_exact"}

    text = str(answer.get("text", "")).strip()
    if not text:
        raise DomainError(422, "question_invalid", "简答题缺少参考答案")
    return {"text": text}, {"mode": "manual"}


def validate_question_data(
    db: Session,
    *,
    subject_id: str,
    chapter_id: str | None,
    knowledge_point_ids: list[str],
    question_type: QuestionType,
    stem: str,
    options: list[QuestionOption | dict[str, Any]],
    answer: dict[str, Any],
    explanation: str,
    difficulty: QuestionDifficulty,
) -> tuple[ValidatedQuestion, list[KnowledgePoint]]:
    points = load_approved_points(
        db,
        subject_id,
        knowledge_point_ids,
        chapter_id=chapter_id,
    )
    allowed_ids = {point.id for point in points}
    selected_ids = list(dict.fromkeys(knowledge_point_ids or [point.id for point in points]))
    if not selected_ids:
        raise DomainError(422, "question_invalid", "题目必须关联至少一个知识点")
    if any(point_id not in allowed_ids for point_id in selected_ids):
        raise DomainError(
            422,
            "question_invalid",
            "题目关联了不在所选范围内的知识点",
        )
    if chapter_id is None:
        chapter_ids = {point.chapter_id for point in points}
        if len(chapter_ids) == 1:
            chapter_id = next(iter(chapter_ids))

    normalized_options = _normalize_options(question_type, options)
    normalized_answer, grading_rule = _normalize_answer(
        question_type,
        answer,
        normalized_options,
    )
    stem = stem.strip()
    explanation = explanation.strip()
    if len(normalize_stem(stem)) < 5:
        raise DomainError(422, "question_invalid", "题干过短")
    if len(normalize_stem(explanation)) < 5:
        raise DomainError(422, "question_invalid", "解析过短")
    return (
        ValidatedQuestion(
            type=question_type.value,
            stem=stem,
            options=normalized_options,
            answer=normalized_answer,
            grading_rule=grading_rule,
            explanation=explanation,
            difficulty=difficulty.value,
            knowledge_point_ids=selected_ids,
        ),
        points,
    )


def find_duplicate(
    db: Session,
    *,
    subject_id: str,
    stem: str,
    exclude_id: str | None = None,
) -> Question | None:
    target = normalize_stem(stem)
    statement = select(Question).where(Question.subject_id == subject_id)
    if exclude_id:
        statement = statement.where(Question.id != exclude_id)
    for question in db.scalars(statement).all():
        if normalize_stem(question.stem) == target:
            return question
    return None


def _point_brief(point: KnowledgePoint) -> QuestionKnowledgePointBrief:
    return QuestionKnowledgePointBrief(
        id=point.id,
        name=point.name,
        chapter_id=point.chapter_id,
        document_id=point.document_id,
        source_page=point.source_page,
        source_slide=point.source_slide,
        source_locator=point.source_locator,
        review_status=point.review_status,
    )


def question_read(question: Question) -> QuestionRead:
    knowledge_points = sorted(question.knowledge_points, key=lambda item: item.name)
    first_point = knowledge_points[0] if knowledge_points else None
    return QuestionRead(
        id=question.id,
        subject_id=question.subject_id,
        subject_name=question.subject.name if question.subject else "",
        chapter_id=question.chapter_id,
        chapter_name=question.chapter.name if question.chapter else None,
        source_document_id=(
            question.source_document_id
            or (first_point.document_id if first_point else None)
        ),
        source_document_name=(
            question.source_document.name if question.source_document else None
        ),
        generation_job_id=question.generation_job_id,
        duplicate_of_id=question.duplicate_of_id,
        duplicate_reason=question.duplicate_reason,
        type=question.type,  # type: ignore[arg-type]
        stem=question.stem,
        options=[QuestionOption(**item) for item in question.options],
        answer=question.answer,
        grading_rule=question.grading_rule,
        explanation=question.explanation,
        difficulty=question.difficulty,  # type: ignore[arg-type]
        status=question.status,  # type: ignore[arg-type]
        origin=question.origin,  # type: ignore[arg-type]
        source_locator=(
            question.source_locator
            or (first_point.source_locator if first_point else None)
        ),
        ai_provider=question.ai_provider,
        ai_model=question.ai_model,
        confidence=question.confidence,
        review_note=question.review_note,
        score=question.score or 1.0,
        knowledge_points=[_point_brief(point) for point in knowledge_points],
        reviewed_at=question.reviewed_at,
        published_at=question.published_at,
        created_at=question.created_at,
        updated_at=question.updated_at,
    )


def _question_statement():
    return select(Question).options(
        selectinload(Question.knowledge_points),
        selectinload(Question.subject),
        selectinload(Question.chapter),
        selectinload(Question.source_document),
    )


def get_question_or_404(db: Session, question_id: str) -> Question:
    question = db.scalar(
        _question_statement().where(Question.id == question_id)
    )
    if question is None:
        raise DomainError(404, "question_not_found", "题目不存在")
    return question


def get_question(db: Session, question_id: str) -> QuestionRead:
    return question_read(get_question_or_404(db, question_id))


def list_questions(
    db: Session,
    *,
    subject_id: str | None = None,
    chapter_id: str | None = None,
    knowledge_point_id: str | None = None,
    question_type: str | None = None,
    difficulty: str | None = None,
    status: str | None = None,
    origin: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> QuestionListResponse:
    conditions = []
    if subject_id:
        conditions.append(Question.subject_id == subject_id)
    if chapter_id:
        conditions.append(Question.chapter_id == chapter_id)
    if knowledge_point_id:
        conditions.append(
            Question.id.in_(
                select(question_knowledge_points.c.question_id).where(
                    question_knowledge_points.c.knowledge_point_id
                    == knowledge_point_id
                )
            )
        )
    if question_type:
        conditions.append(Question.type == question_type)
    if difficulty:
        conditions.append(Question.difficulty == difficulty)
    if status:
        conditions.append(Question.status == status)
    if origin:
        conditions.append(Question.origin == origin)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        conditions.append(
            or_(Question.stem.ilike(pattern), Question.explanation.ilike(pattern))
        )

    total = db.scalar(select(func.count(Question.id)).where(*conditions)) or 0
    statements = _question_statement().where(*conditions).order_by(
        Question.created_at.desc(),
        Question.id,
    )
    questions = db.scalars(
        statements.offset(max(0, offset)).limit(max(1, min(limit, 200)))
    ).all()
    stats_rows = db.execute(
        select(Question.status, func.count(Question.id))
        .where(*conditions)
        .group_by(Question.status)
    ).all()
    stats = QuestionStats(total=total)
    for status_value, count in stats_rows:
        if hasattr(stats, status_value):
            setattr(stats, status_value, count)
    return QuestionListResponse(
        questions=[question_read(question) for question in questions],
        total=total,
        stats=stats,
    )


def _apply_content(
    db: Session,
    *,
    subject_id: str,
    chapter_id: str | None,
    knowledge_point_ids: list[str],
    question_type: QuestionType,
    stem: str,
    options: list[QuestionOption | dict[str, Any]],
    answer: dict[str, Any],
    explanation: str,
    difficulty: QuestionDifficulty,
) -> tuple[ValidatedQuestion, list[KnowledgePoint]]:
    return validate_question_data(
        db,
        subject_id=subject_id,
        chapter_id=chapter_id,
        knowledge_point_ids=knowledge_point_ids,
        question_type=question_type,
        stem=stem,
        options=options,
        answer=answer,
        explanation=explanation,
        difficulty=difficulty,
    )


def create_question(db: Session, payload: QuestionCreate) -> QuestionRead:
    subject = _get_subject(db, payload.subject_id)
    chapter = _get_chapter(db, payload.chapter_id, payload.subject_id)
    validated, points = _apply_content(
        db,
        subject_id=payload.subject_id,
        chapter_id=chapter.id if chapter else None,
        knowledge_point_ids=payload.knowledge_point_ids,
        question_type=payload.type,
        stem=payload.stem,
        options=payload.options,
        answer=payload.answer,
        explanation=payload.explanation,
        difficulty=payload.difficulty,
    )
    duplicate = find_duplicate(
        db,
        subject_id=subject.id,
        stem=validated.stem,
    )
    question = Question(
        subject_id=subject.id,
        chapter_id=chapter.id if chapter else None,
        source_document_id=points[0].document_id if points else None,
        type=validated.type,
        stem=validated.stem,
        options=validated.options,
        answer=validated.answer,
        grading_rule=validated.grading_rule,
        explanation=validated.explanation,
        difficulty=validated.difficulty,
        status=QuestionStatus.PENDING.value,
        origin=QuestionOrigin.MANUAL.value,
        source_locator=payload.source_locator or (points[0].source_locator if points else None),
        confidence=None,
        review_note=payload.review_note,
        duplicate_of_id=duplicate.id if duplicate else None,
        duplicate_reason=(
            "题干与已有题目重复" if duplicate is not None else None
        ),
        score=1.0,
    )
    question.knowledge_points = points
    db.add(question)
    db.commit()
    db.refresh(question)
    return get_question(db, question.id)


def update_question(
    db: Session,
    question_id: str,
    payload: QuestionUpdate,
) -> QuestionRead:
    question = get_question_or_404(db, question_id)
    data = payload.model_dump(exclude_unset=True)
    if "knowledge_point_ids" in data and data["knowledge_point_ids"] is not None:
        points = load_approved_points(
            db,
            question.subject_id,
            data["knowledge_point_ids"],
            chapter_id=data.get("chapter_id", question.chapter_id),
        )
    else:
        points = list(question.knowledge_points)
        if not points:
            points = load_approved_points(
                db,
                question.subject_id,
                [],
                chapter_id=data.get("chapter_id", question.chapter_id),
            )

    chapter_id = data.get("chapter_id", question.chapter_id)
    _get_chapter(db, chapter_id, question.subject_id)
    validated, points = _apply_content(
        db,
        subject_id=question.subject_id,
        chapter_id=chapter_id,
        knowledge_point_ids=[point.id for point in points],
        question_type=data.get("type", QuestionType(question.type)),
        stem=data.get("stem", question.stem),
        options=data.get("options", question.options),
        answer=data.get("answer", question.answer),
        explanation=data.get("explanation", question.explanation),
        difficulty=data.get(
            "difficulty",
            QuestionDifficulty(question.difficulty),
        ),
    )

    content_fields = {
        "type",
        "stem",
        "options",
        "answer",
        "explanation",
        "difficulty",
        "knowledge_point_ids",
        "chapter_id",
    }
    content_changed = any(field in data for field in content_fields)
    question.chapter_id = chapter_id
    question.type = validated.type
    question.stem = validated.stem
    question.options = validated.options
    question.answer = validated.answer
    question.grading_rule = validated.grading_rule
    question.explanation = validated.explanation
    question.difficulty = validated.difficulty
    question.knowledge_points = points
    question.source_locator = data.get("source_locator", question.source_locator)
    if "review_note" in data:
        question.review_note = data["review_note"]
    if content_changed:
        duplicate = find_duplicate(
            db,
            subject_id=question.subject_id,
            stem=question.stem,
            exclude_id=question.id,
        )
        question.duplicate_of_id = duplicate.id if duplicate else None
        question.duplicate_reason = (
            "题干与已有题目重复" if duplicate is not None else None
        )
        question.status = QuestionStatus.PENDING.value
        question.reviewed_at = None
        question.published_at = None
    db.commit()
    db.refresh(question)
    return get_question(db, question.id)


def review_question(
    db: Session,
    question_id: str,
    status: QuestionStatus,
    note: str | None = None,
) -> QuestionRead:
    question = get_question_or_404(db, question_id)
    question.status = status.value
    question.reviewed_at = utc_now()
    if note is not None:
        question.review_note = note
    if status == QuestionStatus.APPROVED:
        question.published_at = utc_now()
    else:
        question.published_at = None
    db.commit()
    db.refresh(question)
    return get_question(db, question.id)


def bulk_review(
    db: Session,
    ids: list[str],
    status: QuestionStatus,
    note: str | None = None,
) -> int:
    unique_ids = list(dict.fromkeys(ids))
    questions = db.scalars(
        select(Question).where(Question.id.in_(unique_ids))
    ).all()
    if len(questions) != len(unique_ids):
        raise DomainError(
            404,
            "question_not_found",
            "部分题目不存在，请刷新后重试",
        )
    for question in questions:
        question.status = status.value
        question.reviewed_at = utc_now()
        question.published_at = utc_now() if status == QuestionStatus.APPROVED else None
        if note is not None:
            question.review_note = note
    db.commit()
    return len(questions)


def regenerate_question(
    db: Session,
    question_id: str,
    *,
    count: int = 1,
    difficulty: QuestionDifficulty | None = None,
) -> QuestionGenerationJob:
    question = get_question_or_404(db, question_id)
    from app.services import question_generation

    return question_generation.create_generation_job(
        db,
        subject_id=question.subject_id,
        chapter_id=question.chapter_id,
        knowledge_point_ids=[point.id for point in question.knowledge_points],
        types=[QuestionType(question.type)],
        count=count,
        difficulty=difficulty or QuestionDifficulty(question.difficulty),
        source_question_id=question.id,
    )
