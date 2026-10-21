from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
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
    GeneratedQuestionDraft,
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
# One repair call per job: enough for a malformed field, bounded in cost.
MAX_FORMAT_REPAIRS = 1


class AIOutputFormatError(AIClientError):
    """Model output could not be turned into valid question drafts."""

    def __init__(self, message: str, *, detail: str = "") -> None:
        super().__init__(message, kind="bad_shape", error_code="bad_shape")
        self.detail = detail


TYPE_ALIASES = {
    "single_choice": "single_choice",
    "single-choice": "single_choice",
    "singlechoice": "single_choice",
    "single": "single_choice",
    "单选": "single_choice",
    "单选题": "single_choice",
    "multiple_choice": "multiple_choice",
    "multiple-choice": "multiple_choice",
    "multiplechoice": "multiple_choice",
    "multiple": "multiple_choice",
    "multi": "multiple_choice",
    "多选": "multiple_choice",
    "多选题": "multiple_choice",
    "true_false": "true_false",
    "true-false": "true_false",
    "truefalse": "true_false",
    "boolean": "true_false",
    "judgment": "true_false",
    "judge": "true_false",
    "判断": "true_false",
    "判断题": "true_false",
    "short_answer": "short_answer",
    "short-answer": "short_answer",
    "shortanswer": "short_answer",
    "short": "short_answer",
    "essay": "short_answer",
    "简答": "short_answer",
    "简答题": "short_answer",
}
DIFFICULTY_ALIASES = {
    "easy": "easy",
    "简单": "easy",
    "基础": "easy",
    "medium": "medium",
    "中等": "medium",
    "一般": "medium",
    "hard": "hard",
    "困难": "hard",
    "难": "hard",
}
TRUE_VALUES = {"true", "t", "yes", "y", "1", "正确", "对", "是"}
FALSE_VALUES = {"false", "f", "no", "n", "0", "错误", "错", "否"}



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
1. answer 必须是对象，不能是布尔、字符串或数组：
   - 单选题：{{"choices": ["A"]}}，恰好一个；
   - 多选题：{{"choices": ["A", "C"]}}，至少一个；
   - 判断题：{{"boolean": true}} 或 {{"boolean": false}}，options 可为 [] 或 [{{"key":"T","text":"正确"}},{{"key":"F","text":"错误"}}]；
   - 简答题：{{"text": "参考答案"}}，options 必须为 []。
2. 选择题选项 key 不重复、内容不重复，答案 key 必须存在于 options。
3. 每道题至少关联一个给定知识点 id。
4. 不要输出 JSON 之外的文字。
""".strip()
    return system, user


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_type(value: Any) -> str | None:
    return TYPE_ALIASES.get(_text(value).lower())


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    text = _text(value).lower()
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    return None


def _choice_keys(value: Any) -> list[str]:
    if isinstance(value, str):
        parts = re.split(r"[,，、;；/\s]+", value.strip())
    elif isinstance(value, (list, tuple, set)):
        parts = [str(item) for item in value]
    else:
        parts = []
    return list(dict.fromkeys(part.strip().upper() for part in parts if part.strip()))


def _coerce_options(raw: Any) -> list[dict[str, str]]:
    if raw is None:
        return []
    if isinstance(raw, dict):
        items = [
            {"key": key, "text": text}
            for key, text in raw.items()
        ]
    elif isinstance(raw, list):
        items = []
        for index, item in enumerate(raw):
            if isinstance(item, dict):
                items.append(
                    {
                        "key": item.get("key") or item.get("label") or chr(65 + index),
                        "text": item.get("text")
                        or item.get("content")
                        or item.get("value"),
                    }
                )
            else:
                items.append({"key": chr(65 + index), "text": item})
    else:
        return []

    options: list[dict[str, str]] = []
    for index, item in enumerate(items[:8]):
        options.append(
            {
                "key": _text(item.get("key")) or chr(65 + index),
                "text": _text(item.get("text")),
            }
        )
    return options


def _coerce_answer(question_type: str, raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        if question_type in {"single_choice", "multiple_choice"}:
            choices = raw.get("choices")
            if choices is None:
                choices = raw.get("choice_keys") or raw.get("keys")
            if choices is None and "answer" in raw:
                choices = raw["answer"]
            return {"choices": _choice_keys(choices)}
        if question_type == "true_false":
            if "boolean" in raw:
                value = _coerce_bool(raw["boolean"])
            elif "value" in raw:
                value = _coerce_bool(raw["value"])
            elif "answer" in raw:
                value = _coerce_bool(raw["answer"])
            elif "choices" in raw:
                keys = _choice_keys(raw["choices"])
                value = True if keys[:1] in (["T"], ["TRUE"]) else False if keys[:1] in (["F"], ["FALSE"]) else None
            else:
                value = None
            return {"boolean": value} if value is not None else {}
        # short answer is free text; never invent one
        text = raw.get("text") or raw.get("answer") or ""
        return {"text": _text(text)}

    if isinstance(raw, bool):
        return {"boolean": raw} if question_type == "true_false" else {}
    if isinstance(raw, (int, float)) and question_type == "true_false":
        value = _coerce_bool(raw)
        return {"boolean": value} if value is not None else {}
    if isinstance(raw, str):
        if question_type == "true_false":
            value = _coerce_bool(raw)
            return {"boolean": value} if value is not None else {}
        if question_type in {"single_choice", "multiple_choice"}:
            return {"choices": _choice_keys(raw)}
        return {"text": raw.strip()}
    if isinstance(raw, (list, tuple, set)):
        if question_type in {"single_choice", "multiple_choice"}:
            return {"choices": _choice_keys(raw)}
        return {}
    return {}


def _normalize_draft(
    item: Any,
    *,
    allowed_point_ids: set[str],
) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("题目不是对象")
    question_type = _coerce_type(item.get("type"))
    if question_type is None:
        raise ValueError(f"不支持的题型：{_text(item.get('type')) or '缺失'}")
    stem = _text(item.get("stem") or item.get("question"))
    explanation = _text(item.get("explanation") or item.get("analysis"))
    options = _coerce_options(item.get("options"))
    if question_type == "short_answer":
        options = []
    if question_type == "true_false" and options:
        # Keep T/F options only if they use the canonical keys; otherwise the
        # DB will add the standard 正确/错误 pair.
        keys = {option["key"].upper() for option in options}
        if keys != {"T", "F"}:
            options = []
    answer = _coerce_answer(question_type, item.get("answer"))
    raw_points = item.get("knowledge_point_ids")
    if isinstance(raw_points, str):
        raw_points = [raw_points]
    point_ids = [
        _text(point_id)
        for point_id in (raw_points or [])
        if _text(point_id)
    ]
    if not point_ids and len(allowed_point_ids) == 1:
        point_ids = list(allowed_point_ids)
    difficulty = DIFFICULTY_ALIASES.get(_text(item.get("difficulty")).lower(), "medium")
    confidence = item.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
        confidence = None
    return {
        "type": question_type,
        "stem": stem,
        "options": options,
        "answer": answer,
        "explanation": explanation,
        "difficulty": difficulty,
        "knowledge_point_ids": point_ids,
        "confidence": confidence,
    }


def _parse_generated_batch(
    raw: Any,
    *,
    allowed_point_ids: set[str],
) -> tuple[GeneratedQuestionBatch, list[str], int]:
    """Normalise tolerant shapes, then validate each draft independently.

    A malformed draft is skipped and reported; it is never coerced into a
    question with invented fields. Raises when every draft is unusable.
    """

    if isinstance(raw, list):
        raw = {"questions": raw}
    if not isinstance(raw, dict):
        raise AIOutputFormatError("AI 返回的 JSON 顶层不是对象")
    raw_questions = raw.get("questions")
    if isinstance(raw_questions, dict):
        raw_questions = [raw_questions]
    if raw_questions is None and ("stem" in raw or "question" in raw):
        raw_questions = [raw]
    if not isinstance(raw_questions, list):
        raise AIOutputFormatError("AI 返回缺少 questions 数组")

    drafts: list[GeneratedQuestionDraft] = []
    warnings: list[str] = []
    invalid = 0
    for index, item in enumerate(raw_questions[:20]):
        try:
            normalized = _normalize_draft(item, allowed_point_ids=allowed_point_ids)
            drafts.append(GeneratedQuestionDraft.model_validate(normalized))
        except (ValueError, ValidationError) as exc:
            invalid += 1
            warnings.append(f"第 {index + 1} 题未通过字段校验：{_short_reason(exc)}")

    if not drafts and raw_questions:
        detail = "；".join(warnings[:2])[:300]
        raise AIOutputFormatError(
            f"AI 返回的 {len(raw_questions)} 道题均未通过字段校验"
            + (f"（{detail}）" if detail else ""),
            detail=detail,
        )
    return GeneratedQuestionBatch(questions=drafts), warnings, invalid


def _short_reason(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(item) for item in first.get("loc", ()))
        message = str(first.get("msg", "")).strip()
        return f"{location}: {message}" if location else message
    return str(exc)


def _validated_drafts(
    db: Session,
    job: QuestionGenerationJob,
    batch: GeneratedQuestionBatch,
    points_by_id: dict[str, KnowledgePoint],
    seen_stems: set[str],
    allowed_types: set[str],
    warnings: list[str],
) -> tuple[list[tuple[questions.ValidatedQuestion, list[KnowledgePoint], float | None]], int]:
    valid: list[tuple[questions.ValidatedQuestion, list[KnowledgePoint], float | None]] = []
    skipped = 0
    for index, draft in enumerate(batch.questions):
        try:
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
        except DomainError as exc:
            skipped += 1
            warnings.append(f"第 {index + 1} 题已跳过：{exc.message}")
            continue
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
            repairs_used = 0
            warnings_log: list[str] = []

            def timed_chat(system_text: str, user_text: str) -> dict[str, Any]:
                nonlocal calls
                stage_started = time.perf_counter()
                result = active_client.chat_json(
                    system_text,
                    user_text,
                    cancel_check=lambda: job_control.is_cancel_requested(job_id),
                )
                calls += 1
                timings["model_calls"] = calls
                usage = getattr(active_client, "last_usage", None)
                if isinstance(usage, dict) and usage:
                    tokens = timings.setdefault(
                        "tokens",
                        {
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0,
                            "reasoning_tokens": 0,
                        },
                    )
                    for key in (
                        "prompt_tokens",
                        "completion_tokens",
                        "total_tokens",
                        "reasoning_tokens",
                    ):
                        tokens[key] = int(tokens.get(key, 0)) + int(usage.get(key, 0) or 0)
                fallback = getattr(active_client, "last_json_mode_fallback", None)
                if isinstance(fallback, dict) and fallback:
                    timings["json_mode_fallback"] = dict(fallback)
                timings.setdefault("model_seconds", 0.0)
                timings["model_seconds"] = round(
                    float(timings["model_seconds"])
                    + (time.perf_counter() - stage_started),
                    3,
                )
                return result

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
                try:
                    raw = timed_chat(system, user)
                except AIClientError as exc:
                    if exc.kind == "invalid_json" and repairs_used < MAX_FORMAT_REPAIRS:
                        repairs_used += 1
                        timings["format_repairs"] = repairs_used
                        logger.warning(
                            "Question generation job %s returned invalid JSON; one repair attempt",
                            job.id,
                        )
                        raw = timed_chat(
                            system
                            + "\n\n上次输出不是有效 JSON。只返回一个 JSON 对象，"
                            "不要 Markdown 代码块，也不要任何解释文字。",
                            user,
                        )
                    else:
                        raise
                try:
                    batch, warnings, invalid = _parse_generated_batch(
                        raw,
                        allowed_point_ids=set(points_by_id),
                    )
                except AIOutputFormatError as exc:
                    if repairs_used < MAX_FORMAT_REPAIRS:
                        repairs_used += 1
                        timings["format_repairs"] = repairs_used
                        logger.warning(
                            "Question generation job %s failed schema validation: %s",
                            job.id,
                            exc.detail or exc.message,
                        )
                        raw = timed_chat(
                            system
                            + "\n\n【字段校验失败】"
                            + (exc.detail or exc.message)
                            + "。请严格按上面的 JSON 结构重新输出：answer 必须是对象，"
                            "判断题使用 {\"boolean\": true}，选择题使用 {\"choices\": [\"A\"]}。",
                            user,
                        )
                        batch, warnings, invalid = _parse_generated_batch(
                            raw,
                            allowed_point_ids=set(points_by_id),
                        )
                    else:
                        raise
                warnings_log.extend(warnings)
                skipped += invalid
                if not batch.questions:
                    continue
                valid, batch_skipped = _validated_drafts(
                    db,
                    job,
                    batch,
                    points_by_id,
                    seen_stems,
                    set(types),
                    warnings_log,
                )
                collected.extend(valid)
                skipped += batch_skipped
                if not valid and batch.questions:
                    detail = "；".join(warnings_log[-2:])[:300]
                    raise AIOutputFormatError(
                        f"AI 返回的 {len(batch.questions)} 道题均未通过语义校验"
                        + (f"（{detail}）" if detail else ""),
                        detail=detail,
                    )
                job.progress = min(85, 10 + int(75 * len(collected) / count))
                job.stage = f"已生成 {len(collected)}/{count} 道题"
                job.generated_count = len(collected)
                job.skipped_count = skipped
                db.commit()

            if job.cancel_requested or job_control.is_cancel_requested(job_id):
                _mark_cancelled(db, job, timings)
                return
            if not collected:
                detail = "；".join(warnings_log[-2:])[:300]
                raise AIOutputFormatError(
                    f"AI 没有返回可用题目（已调用 {calls} 次，跳过 {skipped} 道）",
                    detail=detail,
                )
            collected = collected[:count]
            try:
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
                timings["skipped"] = skipped
                if warnings_log:
                    timings["warnings"] = warnings_log[-8:]
                job.timings = timings
                job.generated_count = len(collected)
                job.skipped_count = skipped
                job.status = QuestionJobStatus.COMPLETED.value
                job.stage = "题目草稿已生成，等待审核"
                job.progress = 100
                job.finished_at = utc_now()
                db.commit()
            except SQLAlchemyError as exc:
                logger.exception("Question persistence failed for job %s", job.id)
                db.rollback()
                raise AIClientError(
                    "题目已生成但保存到数据库失败，请查看服务日志后重试",
                    kind="database",
                    error_code="persistence_failed",
                ) from exc
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
                    logger.exception("Question generation job %s failed", job.id)
                    job.status = QuestionJobStatus.FAILED.value
                    job.stage = "失败"
                    job.error = _safe_error(exc)
                    if isinstance(exc, AIClientError):
                        timings["error_kind"] = exc.kind
                        if exc.status_code is not None:
                            timings["http_status"] = exc.status_code
                        if exc.error_code:
                            timings["error_code"] = exc.error_code
                    else:
                        timings["error_type"] = type(exc).__name__
                    if warnings_log:
                        timings["warnings"] = warnings_log[-8:]
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
