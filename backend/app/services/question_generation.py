from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import (
    QuestionDifficulty,
    QuestionJobStatus,
    QuestionOrigin,
    QuestionStatus,
    QuestionType,
)
from app.core.errors import DomainError
from app.db.base import utc_now
from app.db.session import SessionLocal
from app.models import (
    KnowledgePoint,
    Question,
    QuestionGenerationJob,
    Subject,
)
from app.schemas.question import (
    GeneratedQuestionBatch,
    QuestionGenerationJobRead,
)
from app.services import job_control, questions
from app.services.ai_client import (
    AIClientCancelled,
    AIClientError,
    AIClientProtocol,
    get_ai_client,
)
from app.services.ai_config import effective_ai_settings
from app.services.questions import validate_question_data

logger = logging.getLogger(__name__)

BATCH_SIZE = 5
MAX_MODEL_CALLS = 4
MAX_PROMPT_POINTS = 12


def _subject_or_404(db: Session, subject_id: str) -> Subject:
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise DomainError(404, "subject_not_found", "学科不存在")
    return subject


def _job_read(job: QuestionGenerationJob) -> QuestionGenerationJobRead:
    return QuestionGenerationJobRead(
        id=job.id,
        subject_id=job.subject_id,
        chapter_id=job.chapter_id,
        status=job.status,  # type: ignore[arg-type]
        stage=job.stage,
        progress=job.progress,
        error=job.error,
        cancel_requested=job.cancel_requested,
        attempts=job.attempts,
        provider=job.provider,
        model=job.model,
        request=job.request,
        generated_count=job.generated_count,
        skipped_count=job.skipped_count,
        timings=job.timings,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        updated_at=job.updated_at,
    )


def get_job_or_404(db: Session, job_id: str) -> QuestionGenerationJob:
    job = db.get(QuestionGenerationJob, job_id)
    if job is None:
        raise DomainError(404, "question_generation_job_not_found", "出题任务不存在")
    return job


def get_generation_job(db: Session, job_id: str) -> QuestionGenerationJobRead:
    return _job_read(get_job_or_404(db, job_id))


def create_generation_job(
    db: Session,
    *,
    subject_id: str,
    chapter_id: str | None = None,
    knowledge_point_ids: list[str],
    types: list[QuestionType],
    count: int,
    difficulty: QuestionDifficulty | None = None,
    source_question_id: str | None = None,
    settings: Settings | None = None,
    attempts: int = 1,
) -> QuestionGenerationJob:
    current_settings = effective_ai_settings(settings)
    if not current_settings.ai_configured:
        raise DomainError(
            503,
            "ai_not_configured",
            "AI 未配置：请先在设置页或 .env 配置 API Base、Key 和模型",
        )
    subject = _subject_or_404(db, subject_id)
    unique_types = list(dict.fromkeys(types))
    if not unique_types:
        raise DomainError(422, "no_question_types", "至少选择一种题型")
    running = db.scalar(
        select(QuestionGenerationJob)
        .where(
            QuestionGenerationJob.subject_id == subject_id,
            QuestionGenerationJob.status.in_(
                [
                    QuestionJobStatus.QUEUED.value,
                    QuestionJobStatus.RUNNING.value,
                    QuestionJobStatus.CANCELLING.value,
                ]
            ),
        )
        .limit(1)
    )
    if running is not None:
        raise DomainError(
            409,
            "question_generation_job_running",
            "该学科已有出题任务在运行",
            job_id=running.id,
        )

    points = questions.load_approved_points(
        db,
        subject_id,
        knowledge_point_ids,
        chapter_id=chapter_id,
    )
    selected_ids = list(dict.fromkeys(point.id for point in points))
    request = {
        "subject_id": subject.id,
        "chapter_id": chapter_id,
        "knowledge_point_ids": selected_ids,
        "types": [item.value for item in unique_types],
        "count": min(max(count, 1), 20),
        "difficulty": difficulty.value if difficulty else None,
        "source_question_id": source_question_id,
    }
    job = QuestionGenerationJob(
        subject_id=subject.id,
        chapter_id=chapter_id,
        status=QuestionJobStatus.QUEUED.value,
        stage="等待开始",
        progress=0,
        attempts=attempts,
        provider=current_settings.ai_provider,
        model=current_settings.ai_model,
        request=request,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def retry_generation_job(
    db: Session,
    job_id: str,
    *,
    settings: Settings | None = None,
) -> QuestionGenerationJob:
    job = get_job_or_404(db, job_id)
    if job.status != QuestionJobStatus.FAILED.value:
        raise DomainError(409, "question_generation_job_not_retryable", "只有失败的出题任务可以重试")
    request = job.request
    return create_generation_job(
        db,
        subject_id=request["subject_id"],
        chapter_id=request.get("chapter_id"),
        knowledge_point_ids=request["knowledge_point_ids"],
        types=[QuestionType(item) for item in request["types"]],
        count=request["count"],
        difficulty=(
            QuestionDifficulty(request["difficulty"])
            if request.get("difficulty")
            else None
        ),
        source_question_id=request.get("source_question_id"),
        settings=settings,
        attempts=job.attempts + 1,
    )


def cancel_generation_job(db: Session, job_id: str) -> QuestionGenerationJobRead:
    job = get_job_or_404(db, job_id)
    if job.status in {
        QuestionJobStatus.COMPLETED.value,
        QuestionJobStatus.FAILED.value,
        QuestionJobStatus.CANCELLED.value,
    }:
        raise DomainError(409, "question_generation_job_not_cancellable", "当前任务不能停止")
    job.cancel_requested = True
    if job.status == QuestionJobStatus.QUEUED.value:
        job.status = QuestionJobStatus.CANCELLED.value
        job.stage = "已取消"
        job.finished_at = utc_now()
    else:
        job.status = QuestionJobStatus.CANCELLING.value
        job.stage = "正在停止"
    db.commit()
    job_control.request_cancel(job_id)
    db.refresh(job)
    return _job_read(job)


def _generation_prompt(
    points: list[KnowledgePoint],
    *,
    types: list[str],
    count: int,
    difficulty: str | None,
) -> tuple[str, str]:
    payload = [
        {
            "id": point.id,
            "name": point.name,
            "explanation": point.explanation,
            "core_points": point.core_points,
            "conditions": point.conditions,
            "source_page": point.source_page,
            "source_slide": point.source_slide,
            "source_locator": point.source_locator,
        }
        for point in points[:MAX_PROMPT_POINTS]
    ]
    system = (
        "你是严谨的生物医学题目编写助手。"
        "只能依据给定的已审核知识点编写题目，不得引入未提供的具体事实、数字或结论。"
        "题目、选项、正确答案和解析必须互相一致；无法确定答案时不要编造。"
        "只返回 JSON 对象，不要 Markdown。"
    )
    user = f"""
请根据下列已审核知识点生成 {count} 道题目。
题型范围：{", ".join(types)}
难度：{difficulty or "由你根据知识点判断，但只能使用 easy/medium/hard"}

知识点：
{json.dumps(payload, ensure_ascii=False)}

严格返回：
{{
  "questions": [
    {{
      "type": "single_choice|multiple_choice|true_false|short_answer",
      "stem": "题干",
      "options": [{{"key": "A", "text": "选项"}}],
      "answer": {{"choices": ["A"]}},
      "explanation": "解析",
      "difficulty": "easy|medium|hard",
      "knowledge_point_ids": ["知识点 id"],
      "confidence": 0.0
    }}
  ]
}}

规则：
1. 单选题 answer.choices 恰好一个；多选题至少一个；判断题 answer 使用 boolean；简答题 answer 使用 text，options 为空。
2. 选择题选项 key 不重复、内容不重复，答案 key 必须存在。
3. 每道题至少关联一个给定知识点 id。
4. 不要输出 JSON 之外的文字。
""".strip()
    return system, user


def _validated_drafts(
    db: Session,
    job: QuestionGenerationJob,
    batch: GeneratedQuestionBatch,
    points_by_id: dict[str, KnowledgePoint],
    seen_stems: set[str],
    allowed_types: set[str],
) -> tuple[list[tuple[questions.ValidatedQuestion, list[KnowledgePoint], float | None]], int]:
    valid: list[tuple[questions.ValidatedQuestion, list[KnowledgePoint], float | None]] = []
    skipped = 0
    for draft in batch.questions:
        if draft.type.value not in allowed_types:
            raise DomainError(
                422,
                "question_generation_invalid",
                f"AI 返回了未请求的题型：{draft.type.value}",
            )
        if any(point_id not in points_by_id for point_id in draft.knowledge_point_ids):
            raise DomainError(
                422,
                "question_generation_invalid",
                "AI 返回的题目关联了未提供的知识点",
            )
        validated, points = validate_question_data(
            db,
            subject_id=job.subject_id,
            chapter_id=job.chapter_id,
            knowledge_point_ids=draft.knowledge_point_ids,
            question_type=draft.type,
            stem=draft.stem,
            options=draft.options,
            answer=draft.answer,
            explanation=draft.explanation,
            difficulty=draft.difficulty,
        )
        key = questions.normalize_stem(validated.stem)
        if key in seen_stems or questions.find_duplicate(
            db,
            subject_id=job.subject_id,
            stem=validated.stem,
        ):
            skipped += 1
            continue
        seen_stems.add(key)
        valid.append((validated, points, draft.confidence))
    return valid, skipped


def run_generation(
    job_id: str,
    *,
    session_factory: Callable[[], Session] = SessionLocal,
    client: AIClientProtocol | None = None,
    settings: Settings | None = None,
) -> None:
    current_settings = effective_ai_settings(settings)
    job_control.register(job_id)
    timings: dict[str, Any] = {}
    started = time.perf_counter()
    with session_factory() as db:
        job = db.get(QuestionGenerationJob, job_id)
        if job is None:
            job_control.clear(job_id)
            return
        try:
            if job.status == QuestionJobStatus.CANCELLED.value:
                return
            if job.cancel_requested or job_control.is_cancel_requested(job_id):
                _mark_cancelled(db, job)
                return
            job.status = QuestionJobStatus.RUNNING.value
            job.stage = "准备已审核知识点"
            job.progress = 5
            job.started_at = utc_now()
            db.commit()

            request = job.request
            point_ids = request.get("knowledge_point_ids", [])
            points = db.scalars(
                select(KnowledgePoint).where(KnowledgePoint.id.in_(point_ids))
            ).all()
            if len(points) != len(set(point_ids)):
                raise DomainError(409, "knowledge_point_changed", "知识点已变化，请重新发起出题")
            if any(point.review_status != "approved" for point in points):
                raise DomainError(409, "knowledge_not_approved", "知识点不再是已通过状态")
            if not points:
                raise DomainError(409, "no_approved_knowledge_points", "没有可用的已审核知识点")
            points_by_id = {point.id: point for point in points}
            types = [str(item) for item in request.get("types", [])]
            count = int(request.get("count", 1))
            active_client = client or get_ai_client(current_settings)
            type_cycle = types or [QuestionType.SINGLE_CHOICE.value]
            collected: list[tuple[questions.ValidatedQuestion, list[KnowledgePoint], float | None]] = []
            seen_stems: set[str] = set()
            skipped = 0
            calls = 0
            while len(collected) < count and calls < MAX_MODEL_CALLS:
                if job.cancel_requested or job_control.is_cancel_requested(job_id):
                    _mark_cancelled(db, job, timings)
                    return
                remaining = count - len(collected)
                batch_types = [
                    type_cycle[index % len(type_cycle)]
                    for index in range(min(BATCH_SIZE, remaining))
                ]
                system, user = _generation_prompt(
                    points,
                    types=batch_types,
                    count=len(batch_types),
                    difficulty=request.get("difficulty"),
                )
                stage_started = time.perf_counter()
                raw = active_client.chat_json(
                    system,
                    user,
                    cancel_check=lambda: job_control.is_cancel_requested(job_id),
                )
                timings.setdefault("model_seconds", 0.0)
                timings["model_seconds"] = round(
                    float(timings["model_seconds"]) + (time.perf_counter() - stage_started),
                    3,
                )
                calls += 1
                try:
                    batch = GeneratedQuestionBatch.model_validate(raw)
                except ValidationError as exc:
                    logger.warning(
                        "Question generation job %s invalid shape: %s",
                        job.id,
                        exc.errors()[:3],
                    )
                    raise AIClientError(_describe_validation_error(exc)) from exc
                if not batch.questions:
                    continue
                valid, batch_skipped = _validated_drafts(
                    db,
                    job,
                    batch,
                    points_by_id,
                    seen_stems,
                    set(types),
                )
                collected.extend(valid)
                skipped += batch_skipped
                job.progress = min(85, 10 + int(75 * len(collected) / count))
                job.stage = f"已生成 {len(collected)}/{count} 道题"
                job.generated_count = len(collected)
                job.skipped_count = skipped
                db.commit()

            if job.cancel_requested or job_control.is_cancel_requested(job_id):
                _mark_cancelled(db, job, timings)
                return
            if not collected:
                raise AIClientError("AI 没有返回可用题目，请稍后重试")
            collected = collected[:count]
            for validated, points_for_question, confidence in collected:
                first_point = points_for_question[0]
                duplicate = questions.find_duplicate(
                    db,
                    subject_id=job.subject_id,
                    stem=validated.stem,
                )
                question = Question(
                    subject_id=job.subject_id,
                    chapter_id=job.chapter_id or first_point.chapter_id,
                    source_document_id=first_point.document_id,
                    generation_job_id=job.id,
                    type=validated.type,
                    stem=validated.stem,
                    options=validated.options,
                    answer=validated.answer,
                    grading_rule=validated.grading_rule,
                    explanation=validated.explanation,
                    difficulty=validated.difficulty,
                    status=QuestionStatus.PENDING.value,
                    origin=QuestionOrigin.AI.value,
                    source_locator=first_point.source_locator,
                    ai_provider=job.provider,
                    ai_model=job.model,
                    confidence=confidence,
                    duplicate_of_id=duplicate.id if duplicate else None,
                    duplicate_reason="题干与已有题目重复" if duplicate else None,
                    score=1.0,
                    review_note="AI 生成，候选题目需要人工核验",
                )
                question.knowledge_points = points_for_question
                db.add(question)
            timings["total_seconds"] = round(time.perf_counter() - started, 3)
            job.timings = timings
            job.generated_count = len(collected)
            job.skipped_count = skipped
            job.status = QuestionJobStatus.COMPLETED.value
            job.stage = "题目草稿已生成，等待审核"
            job.progress = 100
            job.finished_at = utc_now()
            db.commit()
        except AIClientCancelled:
            db.rollback()
            job = db.get(QuestionGenerationJob, job_id)
            if job is not None:
                _mark_cancelled(db, job, timings)
        except Exception as exc:
            db.rollback()
            job = db.get(QuestionGenerationJob, job_id)
            if job is not None:
                if job.cancel_requested or job_control.is_cancel_requested(job_id):
                    _mark_cancelled(db, job, timings)
                else:
                    job.status = QuestionJobStatus.FAILED.value
                    job.stage = "失败"
                    job.error = _safe_error(exc)
                    job.timings = timings
                    job.finished_at = utc_now()
                    db.commit()
        finally:
            job_control.clear(job_id)


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, DomainError):
        return exc.message
    if isinstance(exc, AIClientError):
        return exc.message
    return "出题任务失败，请查看服务日志"


def _describe_validation_error(exc: ValidationError) -> str:
    """Summarise the first schema problems without leaking the full prompt."""

    parts: list[str] = []
    for error in exc.errors()[:3]:
        location = ".".join(str(item) for item in error.get("loc", ()))
        message = str(error.get("msg", "")).strip()
        parts.append(f"{location}: {message}" if location else message)
    detail = "；".join(part for part in parts if part)[:300]
    if not detail:
        return "AI 出题返回格式不符合要求，请重试。"
    return (
        f"AI 出题返回格式不符合要求（{detail}）。"
        "模型可能输出了 Markdown 代码块或字段不一致，请重试。"
    )


def _mark_cancelled(
    db: Session,
    job: QuestionGenerationJob,
    timings: dict[str, Any] | None = None,
) -> None:
    job.status = QuestionJobStatus.CANCELLED.value
    job.stage = "已取消"
    job.timings = timings or job.timings
    job.finished_at = utc_now()
    db.commit()
