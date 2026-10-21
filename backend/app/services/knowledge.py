from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import (
    JobStatus,
    KnowledgeOrigin,
    ReviewStatus,
)
from app.core.errors import DomainError
from app.db.base import utc_now
from app.db.session import SessionLocal
from app.models import (
    Document,
    DocumentChunk,
    KnowledgeExtractionJob,
    KnowledgePoint,
)
from app.schemas.ai import (
    AIDocumentAnalysis,
    AIExtractionResponse,
    AIMergeResponse,
    AIMergedPoint,
    AIKnowledgeDraft,
)
from app.schemas.knowledge import JobRead
from app.services.ai_client import (
    AIClientCancelled,
    AIClientError,
    AIClientProtocol,
    get_ai_client,
)
from app.services import job_control
from app.services.ai_config import effective_ai_settings
from app.services.knowledge_common import (
    normalize_name,
    normalize_text,
    unique_strings,
)
from app.services.mappers import job_read

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RawPoint:
    number: int
    draft: AIKnowledgeDraft
    chunk: DocumentChunk
    source_quote: str | None
    quote_verified: bool
    needs_review: bool


@dataclass(slots=True)
class MergeCandidate:
    ref: str
    name: str
    type: str
    explanation: str
    core_points: list[str]
    conditions: str | None
    parent_ref: str | None
    source_point_ids: list[int]
    confidence: float | None
    needs_review: bool
    conflict_note: str | None = None


def _get_document_or_404(db: Session, document_id: str) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise DomainError(404, "document_not_found", "资料不存在")
    return document


def get_job_or_404(db: Session, job_id: str) -> KnowledgeExtractionJob:
    job = db.get(KnowledgeExtractionJob, job_id)
    if job is None:
        raise DomainError(404, "job_not_found", "AI 任务不存在")
    return job


def _running_job(db: Session, document_id: str) -> KnowledgeExtractionJob | None:
    return db.scalar(
        select(KnowledgeExtractionJob)
        .where(
            KnowledgeExtractionJob.document_id == document_id,
            KnowledgeExtractionJob.status.in_(
                [
                    JobStatus.QUEUED.value,
                    JobStatus.ANALYZING.value,
                    JobStatus.EXTRACTING.value,
                    JobStatus.MERGING.value,
                    JobStatus.CANCELLING.value,
                ]
            ),
        )
        .order_by(KnowledgeExtractionJob.created_at.desc())
        .limit(1)
    )


def create_extraction_job(
    db: Session,
    document_id: str,
    *,
    settings: Settings | None = None,
    attempts: int = 1,
) -> JobRead:
    current_settings = effective_ai_settings(settings)
    document = _get_document_or_404(db, document_id)
    if document.status != "parsed":
        raise DomainError(
            409,
            "document_not_parsed",
            "资料尚未成功解析，不能开始知识点提取",
        )
    chunk_count = db.scalar(
        select(func.count(DocumentChunk.id)).where(
            DocumentChunk.document_id == document_id
        )
    ) or 0
    if chunk_count == 0:
        raise DomainError(
            409,
            "document_has_no_chunks",
            "资料没有可提取的正文分块",
        )
    if not current_settings.ai_configured:
        raise DomainError(
            503,
            "ai_not_configured",
            "AI 未配置：请在 .env 设置 AI_API_BASE、AI_API_KEY、AI_MODEL",
        )
    running = _running_job(db, document_id)
    if running is not None:
        raise DomainError(
            409,
            "job_already_running",
            "该资料已有 AI 任务在运行",
            job_id=running.id,
        )

    job = KnowledgeExtractionJob(
        document_id=document_id,
        status=JobStatus.QUEUED.value,
        stage="等待开始",
        progress=0,
        attempts=attempts,
        provider=current_settings.ai_provider,
        model=current_settings.ai_model,
        total_chunks=chunk_count,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    result = job_read(job)
    assert result is not None
    return result


def retry_extraction(
    db: Session,
    job_id: str,
    *,
    settings: Settings | None = None,
) -> JobRead:
    job = get_job_or_404(db, job_id)
    if job.status != JobStatus.FAILED.value:
        raise DomainError(409, "job_not_retryable", "只有失败的任务可以重试")
    return create_extraction_job(
        db,
        job.document_id,
        settings=settings,
        attempts=job.attempts + 1,
    )


def cancel_extraction_job(db: Session, job_id: str) -> JobRead:
    """Request a cooperative stop; the runner marks the job cancelled."""

    job = get_job_or_404(db, job_id)
    if job.status == JobStatus.CANCELLING.value:
        job.cancel_requested = True
        db.commit()
        job_control.request_cancel(job.id)
        return _job_read_required(job)
    if job.status == JobStatus.QUEUED.value:
        job.cancel_requested = True
        job.status = JobStatus.CANCELLED.value
        job.stage = "已停止"
        job.finished_at = utc_now()
        db.commit()
        db.refresh(job)
        job_control.request_cancel(job.id)
        return _job_read_required(job)
    if job.status not in {
        JobStatus.ANALYZING.value,
        JobStatus.EXTRACTING.value,
        JobStatus.MERGING.value,
    }:
        raise DomainError(
            409,
            "job_not_cancellable",
            "只有排队中或运行中的 AI 任务可以停止",
        )

    # Persist first so a restart or another process can see the request, then
    # wake the in-process runner.
    job.cancel_requested = True
    job.status = JobStatus.CANCELLING.value
    job.stage = "正在停止，等待当前模型请求结束"
    db.commit()
    db.refresh(job)
    job_control.request_cancel(job.id)
    return _job_read_required(job)


def _job_read_required(job: KnowledgeExtractionJob) -> JobRead:
    result = job_read(job)
    assert result is not None
    return result


def list_jobs(db: Session, document_id: str) -> list[JobRead]:
    _get_document_or_404(db, document_id)
    jobs = db.scalars(
        select(KnowledgeExtractionJob)
        .where(KnowledgeExtractionJob.document_id == document_id)
        .order_by(KnowledgeExtractionJob.created_at.desc())
    ).all()
    return [read for job in jobs if (read := job_read(job)) is not None]


def _analysis_prompt(
    document: Document,
    chunks: list[DocumentChunk],
    settings: Settings,
) -> tuple[str, str]:
    outline_parts: list[str] = []
    max_chars = settings.ai_outline_max_chars
    per_chunk = max(120, min(420, max_chars // max(1, len(chunks))))
    used = 0
    for index, chunk in enumerate(chunks, start=1):
        heading = chunk.heading_path or chunk.location_label
        preview = normalize_text(chunk.content)[:per_chunk]
        line = f"[{index}] {heading}（{chunk.location_label}）：{preview}"
        if used + len(line) + 1 > max_chars:
            outline_parts.append("……（提纲已截断，其余分块由逐块提取覆盖）")
            break
        outline_parts.append(line)
        used += len(line) + 1
    outline = "\n".join(outline_parts)
    system = (
        "你是严谨的生物医学学习内容结构分析助手。"
        "请只依据用户提供的文档标题、章节层级与内容片段进行分析，"
        "不得编造原文没有的信息。只返回一个 JSON 对象，不要 Markdown 代码块。"
    )
    user = f"""
资料名称：{document.name}
文档标题：{document.content_title or document.name}
学科：{document.subject.name if document.subject else "未知"}
章节：{document.chapter.name if document.chapter else "未指定"}

请分析整章结构，并严格返回以下 JSON 结构：
{{
  "theme": "本章主题",
  "learning_objectives": ["学习目标"],
  "sections": ["主要小节及其关系"],
  "core_concepts": ["核心概念"],
  "processes": ["重要过程和机制"],
  "relationships": ["因果关系、条件关系或概念关系"],
  "formulas": ["公式、关键数值或实验方法"],
  "confusions": ["易混淆概念"],
  "prerequisites": ["前置知识"],
  "cross_links": ["跨小节关联"]
}}

内容提纲：
{outline}
""".strip()
    return system, user


def _analysis_context(analysis: AIDocumentAnalysis, max_chars: int = 2500) -> str:
    """Compact analysis context used by every extraction/merge prompt."""

    parts: list[str] = []
    if analysis.theme.strip():
        parts.append(f"主题：{analysis.theme.strip()}")
    for label, values in (
        ("学习目标", analysis.learning_objectives),
        ("小节", analysis.sections),
        ("核心概念", analysis.core_concepts),
        ("机制", analysis.processes),
        ("易混淆", analysis.confusions),
        ("前置", analysis.prerequisites),
    ):
        if values:
            parts.append(f"{label}：" + "；".join(values))
    text = "\n".join(parts)
    return text[:max_chars]


def _analyze_document(
    client: AIClientProtocol,
    document: Document,
    chunks: list[DocumentChunk],
    settings: Settings,
    *,
    cancel_check: Callable[[], bool] | None = None,
) -> AIDocumentAnalysis:
    system, user = _analysis_prompt(document, chunks, settings)
    raw = client.chat_json(system, user, cancel_check=cancel_check)
    try:
        return AIDocumentAnalysis.model_validate(raw)
    except ValidationError as exc:
        raise AIClientError("AI 结构分析返回格式不符合要求") from exc


def _extract_prompt(
    document: Document,
    analysis: AIDocumentAnalysis,
    chunk: DocumentChunk,
    settings: Settings,
) -> tuple[str, str]:
    system = (
        "你是严谨的生物医学知识点抽取助手。"
        "只能从给定原文中抽取知识点，不能补充原文没有的事实、页码或引文。"
        "source_quote 必须逐字来自原文；无法逐字引用时返回 null，并提高待审核标记。"
        "confidence 只是辅助信号，不能作为正确性的证明。"
        "只返回一个 JSON 对象，不要 Markdown 代码块。"
    )
    user = f"""
整章结构要点：
{_analysis_context(analysis)}

当前分块：
- 资料来源：{chunk.location_label}
- 标题路径：{chunk.heading_path or "无"}
- 来源范围：{chunk.char_start}-{chunk.char_end}

原文内容：
{chunk.content}

请抽取最多 {settings.ai_max_points_per_chunk} 个知识点，严格返回：
{{
  "points": [
    {{
      "name": "知识点名称",
      "type": "basic_concept|structure|classification|mechanism|process|causality|formula|experiment|application|comparison",
      "explanation": "准确、清晰的解释",
      "core_points": ["核心要点"],
      "conditions": "适用条件、例外或注意事项，没有则为 null",
      "source_quote": "原文逐字引文，无法逐字引用时为 null",
      "confidence": 0.0,
      "needs_review": true,
      "parent_name": "同块内父知识点名称或 null"
    }}
  ]
}}
不要输出 JSON 以外的文字。
""".strip()
    return system, user


def _extract_chunk_raw(
    client: AIClientProtocol,
    document: Document,
    analysis: AIDocumentAnalysis,
    chunk: DocumentChunk,
    settings: Settings,
    *,
    cancel_check: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    system, user = _extract_prompt(document, analysis, chunk, settings)
    return client.chat_json(system, user, cancel_check=cancel_check)


def _build_raw_points(
    raw: dict[str, Any],
    chunk: DocumentChunk,
    settings: Settings,
    start_number: int,
) -> list[RawPoint]:
    try:
        response = AIExtractionResponse.model_validate(raw)
    except ValidationError as exc:
        raise AIClientError("AI 知识点提取返回格式不符合要求") from exc

    content_normalized = normalize_text(chunk.content)
    result: list[RawPoint] = []
    for index, draft in enumerate(response.points[: settings.ai_max_points_per_chunk]):
        quote = draft.source_quote.strip() if draft.source_quote else None
        quote_verified = bool(
            quote and normalize_text(quote) in content_normalized
        )
        needs_review = (
            draft.needs_review
            or draft.confidence is None
            or draft.confidence < 0.6
            or not quote_verified
        )
        result.append(
            RawPoint(
                number=start_number + index,
                draft=draft,
                chunk=chunk,
                source_quote=quote if quote_verified else None,
                quote_verified=quote_verified,
                needs_review=needs_review,
            )
        )
    return result


def _candidate_json(candidate: MergeCandidate) -> dict[str, Any]:
    return {
        "ref": candidate.ref,
        "name": candidate.name,
        "type": candidate.type,
        "explanation": candidate.explanation,
        "core_points": candidate.core_points,
        "conditions": candidate.conditions,
        "parent_ref": candidate.parent_ref,
        "source_point_ids": candidate.source_point_ids,
        "confidence": candidate.confidence,
        "needs_review": candidate.needs_review,
    }


def _merge_prompt(
    document: Document,
    analysis: AIDocumentAnalysis,
    candidates: list[MergeCandidate],
) -> tuple[str, str]:
    system = (
        "你是生物医学知识树整合助手。输入是已经抽取的知识点候选。"
        "执行全章整合：合并重复项、保留上下位关系、补充同一概念的多个来源、"
        "标记矛盾或不确定项。只能重组织和压缩已有候选，不得编造新事实或引文。"
        "source_point_ids 必须只引用输入中存在的数字 ID。"
        "只返回一个 JSON 对象，不要 Markdown 代码块。"
    )
    user = f"""
资料：{document.name}
整章结构要点：
{_analysis_context(analysis)}

知识点候选：
{json.dumps([_candidate_json(item) for item in candidates], ensure_ascii=False)}

请返回：
{{
  "merged_points": [
    {{
      "ref": "本批次唯一引用，例如 m1",
      "name": "合并后的知识点名称",
      "type": "basic_concept|structure|classification|mechanism|process|causality|formula|experiment|application|comparison",
      "explanation": "整合后的解释，只使用候选中的事实",
      "core_points": ["核心要点"],
      "conditions": "适用条件或 null",
      "parent_ref": "同一输出中的父知识点 ref 或 null",
      "source_point_ids": [1, 2],
      "confidence": 0.0,
      "needs_review": true,
      "conflict_note": "矛盾或不确定说明，没有则为 null"
    }}
  ]
}}
不要丢失来源 ID；有矛盾时标记待确认，不要擅自选择答案。
""".strip()
    return system, user


def _dedupe_candidates(
    candidates: list[MergeCandidate],
) -> list[MergeCandidate]:
    result: list[MergeCandidate] = []
    by_name: dict[str, MergeCandidate] = {}
    for candidate in candidates:
        key = normalize_name(candidate.name)
        if not key:
            continue
        existing = by_name.get(key)
        if existing is None:
            by_name[key] = candidate
            result.append(candidate)
            continue
        existing.source_point_ids = sorted(
            set(existing.source_point_ids) | set(candidate.source_point_ids)
        )
        existing.core_points = unique_strings(
            [*existing.core_points, *candidate.core_points]
        )
        if candidate.conditions and candidate.conditions not in (
            existing.conditions or ""
        ):
            existing.conditions = "；".join(
                filter(None, [existing.conditions, candidate.conditions])
            )
        if len(candidate.explanation) > len(existing.explanation):
            existing.explanation = candidate.explanation
        existing.needs_review = True
        if candidate.conflict_note:
            existing.conflict_note = candidate.conflict_note
    return result


def _merge_candidates(
    client: AIClientProtocol,
    document: Document,
    analysis: AIDocumentAnalysis,
    candidates: list[MergeCandidate],
    valid_source_ids: set[int],
    *,
    cancel_check: Callable[[], bool] | None = None,
) -> list[MergeCandidate]:
    system, user = _merge_prompt(document, analysis, candidates)
    raw = client.chat_json(system, user, cancel_check=cancel_check)
    try:
        response = AIMergeResponse.model_validate(raw)
    except ValidationError as exc:
        raise AIClientError("AI 合并结果格式不符合要求") from exc

    refs = {point.ref for point in response.merged_points}
    result: list[MergeCandidate] = []
    for point in response.merged_points:
        if not point.source_point_ids or any(
            source_id not in valid_source_ids
            for source_id in point.source_point_ids
        ):
            raise AIClientError(
                "AI 合并结果引用了不存在的来源编号，已中止以防来源丢失",
            )
        parent_ref = point.parent_ref if point.parent_ref in refs else None
        needs_review = point.needs_review or (
            parent_ref is None and bool(point.parent_ref)
        )
        result.append(
            MergeCandidate(
                ref=point.ref,
                name=point.name.strip(),
                type=point.type.value,
                explanation=point.explanation.strip(),
                core_points=unique_strings(point.core_points),
                conditions=point.conditions,
                parent_ref=parent_ref,
                source_point_ids=sorted(set(point.source_point_ids)),
                confidence=point.confidence,
                needs_review=needs_review,
                conflict_note=point.conflict_note,
            )
        )
    if not result:
        raise AIClientError("AI 合并结果为空")
    return _dedupe_candidates(result)


def _candidate_has_cycle(
    candidate: MergeCandidate,
    by_ref: dict[str, MergeCandidate],
) -> bool:
    seen = {candidate.ref}
    current = candidate.parent_ref
    while current:
        if current in seen:
            return True
        seen.add(current)
        parent = by_ref.get(current)
        current = parent.parent_ref if parent else None
    return False


def _to_raw_candidates(raw_points: list[RawPoint]) -> list[MergeCandidate]:
    result: list[MergeCandidate] = []
    for point in raw_points:
        result.append(
            MergeCandidate(
                ref=f"p{point.number}",
                name=point.draft.name.strip(),
                type=point.draft.type.value,
                explanation=point.draft.explanation.strip(),
                core_points=unique_strings(point.draft.core_points),
                conditions=point.draft.conditions,
                parent_ref=None,
                source_point_ids=[point.number],
                confidence=point.draft.confidence,
                needs_review=point.needs_review,
            )
        )
    return _dedupe_candidates(result)


def _safe_job_error(exc: Exception) -> str:
    if isinstance(exc, AIClientError):
        return exc.message
    if isinstance(exc, DomainError):
        return exc.message
    if isinstance(exc, ValidationError):
        return "AI 返回格式校验失败"
    return "知识点提取失败，请检查模型配置或稍后重试"


def _cancel_requested(db: Session, job: KnowledgeExtractionJob) -> bool:
    if job_control.is_cancel_requested(job.id):
        return True
    try:
        db.refresh(job)
    except Exception:
        # A deleted/locked row must not keep the runner alive forever.
        return True
    return bool(job.cancel_requested)


def _mark_cancelled(
    db: Session,
    job: KnowledgeExtractionJob,
    *,
    drafts_saved: bool = False,
) -> None:
    job.status = JobStatus.CANCELLED.value
    job.stage = (
        "已停止（草稿已保存）"
        if drafts_saved
        else "已停止（未保存新的合并草稿）"
    )
    job.error = None
    job.cancel_requested = True
    job.finished_at = utc_now()
    db.commit()
    job_control.clear(job.id)


def _extract_all_chunks(
    db: Session,
    job: KnowledgeExtractionJob,
    client: AIClientProtocol,
    document: Document,
    analysis: AIDocumentAnalysis,
    chunks: list[DocumentChunk],
    settings: Settings,
    cancel_check: Callable[[], bool],
) -> list[RawPoint] | None:
    """Bounded-concurrency extraction; AI calls run off the DB thread."""

    concurrency = max(1, min(settings.ai_extraction_concurrency, len(chunks)))
    event_cancel = lambda: job_control.is_cancel_requested(job.id)  # noqa: E731
    raw_results: dict[int, dict[str, Any]] = {}
    first_error: Exception | None = None
    completed = 0
    job.status = JobStatus.EXTRACTING.value
    job.stage = f"已提取 0/{len(chunks)} 块（并发 {concurrency}）"
    job.processed_chunks = 0
    job.progress = 20
    db.commit()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {
            executor.submit(
                _extract_chunk_raw,
                client,
                document,
                analysis,
                chunk,
                settings,
                cancel_check=event_cancel,
            ): index
            for index, chunk in enumerate(chunks)
        }
        pending = set(futures)
        while pending:
            if cancel_check():
                for future in pending:
                    future.cancel()
                return None
            done, pending = wait(
                pending,
                timeout=1.0,
                return_when=FIRST_COMPLETED,
            )
            if not done:
                continue
            for future in done:
                index = futures[future]
                try:
                    raw_results[index] = future.result()
                except AIClientCancelled:
                    for item in pending:
                        item.cancel()
                    return None
                except Exception as exc:
                    first_error = exc
                    for item in pending:
                        item.cancel()
                    pending = set()
                    break
                completed += 1
                if cancel_check():
                    for item in pending:
                        item.cancel()
                    return None
                job.processed_chunks = completed
                job.stage = f"已提取 {completed}/{len(chunks)} 块（并发 {concurrency}）"
                job.progress = 20 + int(50 * completed / len(chunks))
                db.commit()
            if first_error is not None:
                break

    if first_error is not None:
        raise first_error
    if len(raw_results) != len(chunks):
        raise AIClientError("部分分块未返回结果，请重试")

    raw_points: list[RawPoint] = []
    for index, chunk in enumerate(chunks):
        raw_points.extend(
            _build_raw_points(
                raw_results[index],
                chunk,
                settings,
                len(raw_points) + 1,
            )
        )
    return raw_points


def run_extraction(
    job_id: str,
    *,
    session_factory: Callable[[], Session] = SessionLocal,
    client: AIClientProtocol | None = None,
    settings: Settings | None = None,
) -> None:
    current_settings = effective_ai_settings(settings)
    timings: dict[str, Any] = {}
    job_control.register(job_id)
    with session_factory() as db:
        job = db.get(KnowledgeExtractionJob, job_id)
        if job is None:
            job_control.clear(job_id)
            return
        try:
            if job.status == JobStatus.CANCELLED.value:
                job_control.clear(job_id)
                return
            if job.status == JobStatus.CANCELLING.value:
                _mark_cancelled(db, job)
                return
            if _cancel_requested(db, job):
                _mark_cancelled(db, job)
                return

            document = _get_document_or_404(db, job.document_id)
            chunks = db.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document.id)
                .order_by(DocumentChunk.chunk_index)
            ).all()
            if not chunks:
                raise DomainError(409, "document_has_no_chunks", "资料没有可提取的分块")
            active_client = client or get_ai_client(current_settings)
            cancel_check = lambda: _cancel_requested(db, job)  # noqa: E731
            timings.update(
                {
                    "chunk_count": len(chunks),
                    "concurrency": max(
                        1,
                        min(
                            current_settings.ai_extraction_concurrency,
                            len(chunks),
                        ),
                    ),
                }
            )
            total_started = time.perf_counter()

            job.status = JobStatus.ANALYZING.value
            job.stage = "分析整章结构"
            job.progress = 5
            job.started_at = utc_now()
            job.total_chunks = len(chunks)
            db.commit()
            if _cancel_requested(db, job):
                _mark_cancelled(db, job)
                return

            stage_started = time.perf_counter()
            analysis = _analyze_document(
                active_client,
                document,
                chunks,
                current_settings,
                cancel_check=cancel_check,
            )
            timings["analysis_seconds"] = round(
                time.perf_counter() - stage_started,
                3,
            )
            job.progress = 20
            job.stage = "逐块提取知识点"
            db.commit()
            if _cancel_requested(db, job):
                job.timings = timings
                _mark_cancelled(db, job)
                return

            stage_started = time.perf_counter()
            try:
                raw_points = _extract_all_chunks(
                    db,
                    job,
                    active_client,
                    document,
                    analysis,
                    chunks,
                    current_settings,
                    cancel_check,
                )
            finally:
                timings["extraction_seconds"] = round(
                    time.perf_counter() - stage_started,
                    3,
                )
            if raw_points is None:
                job.timings = timings
                _mark_cancelled(db, job)
                return
            if _cancel_requested(db, job):
                job.timings = timings
                _mark_cancelled(db, job)
                return
            job.processed_chunks = len(chunks)
            job.extracted_count = len(raw_points)
            timings["extracted_count"] = len(raw_points)
            job.progress = 72
            job.stage = "整章合并与去重"
            db.commit()
            if _cancel_requested(db, job):
                job.timings = timings
                _mark_cancelled(db, job)
                return

            if not raw_points:
                job.timings = {
                    **timings,
                    "total_seconds": round(
                        time.perf_counter() - total_started,
                        3,
                    ),
                }
                job.status = JobStatus.COMPLETED.value
                job.progress = 100
                job.stage = "未提取到可审核知识点"
                job.finished_at = utc_now()
                db.commit()
                logger.info("Knowledge job %s timings: %s", job_id, job.timings)
                return

            stage_started = time.perf_counter()
            valid_source_ids = {point.number for point in raw_points}
            candidates = _to_raw_candidates(raw_points)
            batch_size = current_settings.ai_merge_batch_size
            while len(candidates) > batch_size:
                next_candidates: list[MergeCandidate] = []
                for start in range(0, len(candidates), batch_size):
                    if _cancel_requested(db, job):
                        _mark_cancelled(db, job)
                        return
                    next_candidates.extend(
                        _merge_candidates(
                            active_client,
                            document,
                            analysis,
                            candidates[start : start + batch_size],
                            valid_source_ids,
                            cancel_check=cancel_check,
                        )
                    )
                candidates = _dedupe_candidates(next_candidates)
                if _cancel_requested(db, job):
                    _mark_cancelled(db, job)
                    return

            if len(candidates) > 1:
                if _cancel_requested(db, job):
                    _mark_cancelled(db, job)
                    return
                candidates = _merge_candidates(
                    active_client,
                    document,
                    analysis,
                    candidates,
                    valid_source_ids,
                    cancel_check=cancel_check,
                )
            candidates = _dedupe_candidates(candidates)
            timings["merge_seconds"] = round(
                time.perf_counter() - stage_started,
                3,
            )
            if _cancel_requested(db, job):
                job.timings = timings
                _mark_cancelled(db, job)
                return

            job.status = JobStatus.MERGING.value
            job.stage = "保存审核草稿"
            job.progress = 90
            db.commit()
            persist_started = time.perf_counter()
            _persist_candidates(
                db,
                document,
                raw_points,
                candidates,
            )
            timings["persist_seconds"] = round(
                time.perf_counter() - persist_started,
                3,
            )
            job.merged_count = len(candidates)
            job.duplicate_count = db.scalar(
                select(func.count(KnowledgePoint.id)).where(
                    KnowledgePoint.document_id == document.id,
                    KnowledgePoint.duplicate_of_id.is_not(None),
                )
            ) or 0
            timings["merged_count"] = len(candidates)
            timings["total_seconds"] = round(
                time.perf_counter() - total_started,
                3,
            )
            if _cancel_requested(db, job):
                job.timings = timings
                _mark_cancelled(db, job, drafts_saved=True)
                return
            job.timings = timings
            job.status = JobStatus.COMPLETED.value
            job.stage = "知识点草稿已生成"
            job.progress = 100
            job.finished_at = utc_now()
            db.commit()
            logger.info("Knowledge job %s timings: %s", job_id, timings)
        except AIClientCancelled:
            db.rollback()
            job = db.get(KnowledgeExtractionJob, job_id)
            if job is not None:
                job.timings = timings
                _mark_cancelled(db, job)
        except Exception as exc:
            logger.exception("Knowledge extraction job %s failed", job_id)
            db.rollback()
            job = db.get(KnowledgeExtractionJob, job_id)
            if job is not None:
                if job.cancel_requested or job_control.is_cancel_requested(job_id):
                    job.timings = timings
                    _mark_cancelled(db, job)
                else:
                    job.timings = timings
                    job.status = JobStatus.FAILED.value
                    job.stage = "失败"
                    job.error = _safe_job_error(exc)
                    job.finished_at = utc_now()
                    db.commit()
        finally:
            job_control.clear(job_id)


def _persist_candidates(
    db: Session,
    document: Document,
    raw_points: list[RawPoint],
    candidates: list[MergeCandidate],
) -> None:
    existing_reviewed = db.scalars(
        select(KnowledgePoint).where(
            KnowledgePoint.document_id == document.id,
            (
                (KnowledgePoint.origin == KnowledgeOrigin.MANUAL.value)
                | (
                    KnowledgePoint.review_status
                    != ReviewStatus.PENDING.value
                )
            ),
        )
    ).all()
    existing_by_name = {
        normalize_name(point.name): point for point in existing_reviewed
    }

    all_existing = db.scalars(
        select(KnowledgePoint).where(
            KnowledgePoint.document_id == document.id
        )
    ).all()
    removable_ids = {
        point.id
        for point in all_existing
        if point.origin == KnowledgeOrigin.AI.value
        and point.review_status == ReviewStatus.PENDING.value
    }
    # Never let deleting a draft parent cascade over a manually reviewed
    # descendant. Such descendants become roots and are flagged for attention.
    for point in all_existing:
        if point.id not in removable_ids and point.parent_id in removable_ids:
            point.parent_id = None
            point.needs_review = True
    db.flush()

    db.execute(
        delete(KnowledgePoint).where(
            KnowledgePoint.document_id == document.id,
            KnowledgePoint.origin == KnowledgeOrigin.AI.value,
            KnowledgePoint.review_status == ReviewStatus.PENDING.value,
        )
    )

    raw_by_number = {point.number: point for point in raw_points}
    by_ref = {candidate.ref: candidate for candidate in candidates}
    created: dict[str, KnowledgePoint] = {}
    for candidate in candidates:
        sources = [
            raw_by_number[source_id]
            for source_id in candidate.source_point_ids
            if source_id in raw_by_number
        ]
        if not sources:
            continue
        primary = sources[0]
        verified_quotes = unique_strings(
            [
                source.source_quote
                for source in sources
                if source.quote_verified and source.source_quote
            ]
        )
        locators = unique_strings([source.chunk.location_label for source in sources])
        page_values = [
            source.chunk.page_start
            for source in sources
            if source.chunk.page_start is not None
        ]
        page_end_values = [
            source.chunk.page_end
            for source in sources
            if source.chunk.page_end is not None
        ]
        duplicate = existing_by_name.get(normalize_name(candidate.name))
        review_notes: list[str] = []
        if candidate.conflict_note:
            review_notes.append(candidate.conflict_note)
        if not verified_quotes:
            review_notes.append(
                "AI 未提供可逐字核验的原文引文，解释可能包含模型推断"
            )
        if duplicate is not None:
            review_notes.append(
                f"与已审核知识点「{duplicate.name}」同名，可能重复"
            )
        point = KnowledgePoint(
            subject_id=document.subject_id,
            chapter_id=document.chapter_id,
            document_id=document.id,
            name=candidate.name,
            point_type=candidate.type,
            explanation=candidate.explanation,
            core_points=candidate.core_points,
            conditions=candidate.conditions,
            source_quote="\n\n".join(verified_quotes)[:4000] or None,
            source_quote_verified=bool(verified_quotes),
            source_page=min(page_values) if page_values else None,
            source_page_end=max(page_end_values) if page_end_values else None,
            source_slide=primary.chunk.slide_number,
            source_locator="；".join(locators[:3])[:200],
            source_chunk_id=primary.chunk.id,
            block_start=primary.chunk.block_start,
            block_end=primary.chunk.block_end,
            confidence=candidate.confidence,
            review_note="；".join(review_notes) or None,
            needs_review=candidate.needs_review
            or not verified_quotes
            or duplicate is not None,
            origin=KnowledgeOrigin.AI.value,
            review_status=ReviewStatus.PENDING.value,
            duplicate_of_id=duplicate.id if duplicate is not None else None,
        )
        db.add(point)
        created[candidate.ref] = point

    db.flush()
    for candidate in candidates:
        point = created.get(candidate.ref)
        if point is None:
            continue
        if candidate.parent_ref and candidate.parent_ref in by_ref:
            if _candidate_has_cycle(candidate, by_ref):
                point.parent_id = None
                point.needs_review = True
            else:
                parent = created.get(candidate.parent_ref)
                point.parent_id = parent.id if parent else None
                if parent is None:
                    point.needs_review = True
        elif candidate.parent_ref:
            point.parent_id = None
            point.needs_review = True
        if candidate.conflict_note:
            point.needs_review = True
