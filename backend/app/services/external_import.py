from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.enums import KnowledgeOrigin, KnowledgePointType, ReviewStatus
from app.core.errors import DomainError
from app.db.base import utc_now
from app.models import Chapter, Document, ImportJob, KnowledgePoint, Subject
from app.schemas.external_import import (
    EXTERNAL_IMPORT_EXAMPLE,
    ExternalImportPayload,
    ExternalKnowledgePoint,
    build_external_prompt,
    external_json_schema,
)
from app.schemas.imports import (
    ExternalPointPreview,
    ImportConfirmRequest,
    ImportRead,
    ImportResult,
    ImportSuggestion,
    SuggestedChapter,
)
from app.services import documents as document_service
from app.services import importing as import_service
from app.services.knowledge_common import normalize_name

DUPLICATE_STRATEGIES = {"skip", "update_pending"}

CATEGORY_ALIASES: dict[str, KnowledgePointType] = {
    "basic_concept": KnowledgePointType.BASIC_CONCEPT,
    "concept": KnowledgePointType.BASIC_CONCEPT,
    "基本概念": KnowledgePointType.BASIC_CONCEPT,
    "概念": KnowledgePointType.BASIC_CONCEPT,
    "structure": KnowledgePointType.STRUCTURE,
    "结构": KnowledgePointType.STRUCTURE,
    "结构组成": KnowledgePointType.STRUCTURE,
    "classification": KnowledgePointType.CLASSIFICATION,
    "分类": KnowledgePointType.CLASSIFICATION,
    "mechanism": KnowledgePointType.MECHANISM,
    "原理机制": KnowledgePointType.MECHANISM,
    "机制": KnowledgePointType.MECHANISM,
    "process": KnowledgePointType.PROCESS,
    "过程步骤": KnowledgePointType.PROCESS,
    "过程": KnowledgePointType.PROCESS,
    "causality": KnowledgePointType.CAUSALITY,
    "因果关系": KnowledgePointType.CAUSALITY,
    "formula": KnowledgePointType.FORMULA,
    "公式与计算": KnowledgePointType.FORMULA,
    "公式": KnowledgePointType.FORMULA,
    "experiment": KnowledgePointType.EXPERIMENT,
    "实验方法": KnowledgePointType.EXPERIMENT,
    "application": KnowledgePointType.APPLICATION,
    "应用": KnowledgePointType.APPLICATION,
    "comparison": KnowledgePointType.COMPARISON,
    "对比辨析": KnowledgePointType.COMPARISON,
    "对比": KnowledgePointType.COMPARISON,
}


def _category(value: str) -> tuple[str, str | None]:
    key = value.strip().lower()
    mapped = CATEGORY_ALIASES.get(key)
    if mapped is None:
        return KnowledgePointType.BASIC_CONCEPT.value, f"未知知识点类别 {value!r}，已归为基本概念"
    return mapped.value, None


def _importance(value: str | None) -> tuple[str | None, str | None]:
    if value is None or not value.strip():
        return None, None
    key = value.strip().lower()
    mapping = {
        "high": "high",
        "高": "high",
        "重要": "high",
        "5": "high",
        "4": "high",
        "medium": "medium",
        "中": "medium",
        "一般": "medium",
        "3": "medium",
        "low": "low",
        "低": "low",
        "1": "low",
        "2": "low",
    }
    if key not in mapping:
        return None, f"未知 importance {value!r}，已忽略"
    return mapping[key], None


def _source_locator(point: ExternalKnowledgePoint) -> str:
    source = point.source
    if source.locator:
        return source.locator[:300]
    parts: list[str] = []
    if source.page:
        parts.append(f"第 {source.page} 页")
    if source.slide:
        parts.append(f"第 {source.slide} 张幻灯片")
    return "；".join(parts) if parts else "外部 AI 未提供来源"


def _flatten_external_chapters(
    payload: ExternalImportPayload,
) -> list[SuggestedChapter]:
    title = payload.document.name.strip()[:160] or "未命名资料"
    roots = payload.chapter_tree
    nodes: list[SuggestedChapter] = []

    def add_children(
        children: list[Any],
        parent_index: int,
        level: int,
    ) -> None:
        for child in children:
            index = len(nodes)
            nodes.append(
                SuggestedChapter(
                    name=child.name.strip()[:160],
                    level=min(level, 12),
                    parent_index=parent_index,
                    action="create",
                    confidence=0.9,
                    source_slide=child.source_slide,
                    source_kind="external_json",
                    reason="来自外部 AI 章节树",
                )
            )
            add_children(child.children, index, level + 1)

    if len(roots) == 1 and normalize_name(roots[0].name) == normalize_name(title):
        root = roots[0]
        nodes.append(
            SuggestedChapter(
                name=root.name.strip()[:160],
                level=1,
                parent_index=None,
                action="create",
                confidence=0.9,
                source_slide=root.source_slide,
                source_kind="external_json",
                reason="外部 AI 资料标题章节",
            )
        )
        add_children(root.children, 0, 2)
    else:
        nodes.append(
            SuggestedChapter(
                name=title,
                level=1,
                parent_index=None,
                action="create",
                confidence=0.9,
                source_kind="external_json",
                reason="外部 AI 资料标题",
            )
        )
        add_children(roots, 0, 2)
    return nodes


def _node_paths(nodes: list[SuggestedChapter]) -> list[tuple[str, ...]]:
    paths: list[tuple[str, ...]] = []
    for index in range(len(nodes)):
        names: list[str] = []
        current: int | None = index
        seen: set[int] = set()
        while current is not None and current not in seen:
            seen.add(current)
            names.append(normalize_name(nodes[current].name))
            current = nodes[current].parent_index
        paths.append(tuple(reversed(names)))
    return paths


def build_external_suggestion(
    db: Session,
    document: Document,
    payload: ExternalImportPayload,
    subject: Subject,
    *,
    duplicate_import: bool = False,
) -> ImportSuggestion:
    nodes = _flatten_external_chapters(payload)
    suggestion = import_service._match_chapters(db, subject, nodes)
    suggestion.outline_source = "external_json"
    suggestion.source_type = "external_json"
    suggestion.needs_confirmation = True
    suggestion.duplicate_import = duplicate_import
    suggestion.reasons = [
        "来自外部 AI 预处理 JSON",
        *suggestion.reasons,
    ]
    if duplicate_import:
        suggestion.reasons.insert(0, "该 JSON 文件已导入过；本次仅做重复预览，不会直接覆盖")

    paths = _node_paths(nodes)
    path_index: dict[tuple[str, ...], int] = {
        path: index for index, path in enumerate(paths)
    }
    relative_path_index = {
        path[1:]: index for index, path in enumerate(paths) if len(path) > 1
    }
    last_name_index: dict[str, int] = {}
    for index, node in enumerate(nodes):
        last_name_index.setdefault(normalize_name(node.name), index)

    existing_points = db.scalars(
        select(KnowledgePoint).where(KnowledgePoint.subject_id == subject.id)
    ).all()
    by_chapter_name = {
        (point.chapter_id, normalize_name(point.name)): point
        for point in existing_points
    }
    by_document_name = {
        (point.document_id, normalize_name(point.name)): point
        for point in existing_points
    }

    previews: list[ExternalPointPreview] = []
    duplicate_count = 0
    missing_source_count = 0
    seen_external_ids: dict[str, int] = {}
    seen_payload_keys: set[tuple[int, str]] = set()

    for point in payload.knowledge_points:
        path = tuple(normalize_name(part) for part in point.chapter_path if part.strip())
        index = path_index.get(path)
        if index is None:
            index = relative_path_index.get(path)
        warnings: list[str] = []
        if index is None and path:
            tail = path[-1]
            index = last_name_index.get(tail)
            if index is None:
                warnings.append(
                    f"章节路径 {' > '.join(point.chapter_path)} 未在 chapter_tree 中找到，已归到根章节"
                )
                index = 0
            else:
                warnings.append(
                    f"章节路径 {' > '.join(point.chapter_path)} 仅按末级名称匹配"
                )
        if index is None:
            index = 0

        _, category_warning = _category(point.category)
        if category_warning:
            warnings.append(category_warning)
        _, importance_warning = _importance(point.importance)
        if importance_warning:
            warnings.append(importance_warning)

        target_chapter_id = nodes[index].existing_chapter_id
        key = (target_chapter_id, normalize_name(point.title))
        existing = by_chapter_name.get(key) if target_chapter_id else None
        if existing is None:
            existing = by_document_name.get(
                (document.id, normalize_name(point.title))
            )
        if existing is not None:
            duplicate_count += 1
            warnings.append(f"与已有知识点「{existing.name}」重复")

        if not point.source.page and not point.source.slide and not point.source.locator:
            missing_source_count += 1
            warnings.append("缺少来源页码/幻灯片")
        if point.point_id:
            if point.point_id in seen_external_ids:
                warnings.append(f"point_id {point.point_id!r} 在文件中重复")
            seen_external_ids[point.point_id] = index
        payload_key = (index, normalize_name(point.title))
        if payload_key in seen_payload_keys:
            warnings.append("同一章节下 title 重复")
        seen_payload_keys.add(payload_key)

        if len(previews) < 100:
            previews.append(
                ExternalPointPreview(
                    point_id=point.point_id,
                    title=point.title,
                    chapter_path=point.chapter_path,
                    category=point.category,
                    importance=point.importance,
                    source_page=point.source.page,
                    source_slide=point.source.slide,
                    duplicate_of_id=existing.id if existing else None,
                    duplicate_of_title=existing.name if existing else None,
                    warnings=warnings,
                )
            )

    suggestion.knowledge_point_count = len(payload.knowledge_points)
    suggestion.duplicate_point_count = duplicate_count
    suggestion.missing_source_count = missing_source_count
    suggestion.points_preview = previews
    return suggestion


async def create_external_import(
    db: Session,
    upload: UploadFile,
    *,
    subject_id: str | None,
    duplicate_strategy: str,
    settings: Settings | None = None,
) -> ImportRead:
    current_settings = settings or get_settings()
    validation_started = time.perf_counter()
    if duplicate_strategy not in DUPLICATE_STRATEGIES:
        raise DomainError(
            422,
            "invalid_duplicate_strategy",
            "不支持的重复处理策略",
        )
    original_name = document_service.sanitize_filename(upload.filename or "import.json")
    if Path(original_name).suffix.lower() != ".json":
        raise DomainError(
            415,
            "external_json_required",
            "外部 AI 导入仅支持 .json 文件",
        )

    data = await upload.read(current_settings.max_upload_bytes + 1)
    if not data:
        raise DomainError(422, "empty_file", "JSON 文件内容为空")
    if len(data) > current_settings.max_upload_bytes:
        raise DomainError(
            413,
            "file_too_large",
            f"文件超过 {current_settings.max_upload_bytes // (1024 * 1024)} MB 限制",
        )
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DomainError(422, "invalid_json_encoding", "JSON 文件必须是 UTF-8 编码") from exc
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DomainError(
            422,
            "invalid_json",
            f"JSON 语法错误：第 {exc.lineno} 行第 {exc.colno} 列",
        ) from exc
    try:
        payload = ExternalImportPayload.model_validate(raw)
    except ValidationError as exc:
        details = [
            {
                "path": ".".join(str(item) for item in error["loc"]),
                "message": error["msg"],
            }
            for error in exc.errors()[:8]
        ]
        message = details[0]["message"] if details else "JSON 结构不符合要求"
        raise DomainError(
            422,
            "external_json_invalid",
            f"外部 AI JSON 校验失败：{message}",
            errors=details,
        ) from exc

    subject = _resolve_subject(db, payload, subject_id)
    digest = hashlib.sha256(data).hexdigest()
    duplicate = db.scalar(
        select(Document).where(
            Document.sha256 == digest,
            Document.subject_id == subject.id,
            Document.extension == ".json",
        )
    )
    new_document_path: Path | None = None
    if duplicate is not None:
        document = duplicate
        duplicate_import = True
    else:
        document, new_document_path = _store_external_document(
            db,
            data,
            payload,
            subject,
            original_name,
            digest,
            current_settings,
        )
        duplicate_import = False

    try:
        suggestion = build_external_suggestion(
            db,
            document,
            payload,
            subject,
            duplicate_import=duplicate_import,
        )
        job = ImportJob(
            document_id=document.id,
            status="awaiting_confirmation",
            stage=(
                "文件已导入过，预览重复项"
                if duplicate_import
                else "外部 AI JSON 已校验，等待确认归档"
            ),
            progress=50,
            mode="smart_archive",
            source_type="external_json",
            duplicate_strategy=duplicate_strategy,
            auto_analyze=False,
            require_preview=True,
            uncertain_policy="confirm",
            payload=payload.model_dump(),
            suggestion=suggestion.model_dump(),
            timings={
                "validation_ms": round(
                    (time.perf_counter() - validation_started) * 1000,
                    1,
                )
            },
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return import_service._import_read(db, job)
    except Exception:
        db.rollback()
        if new_document_path is not None:
            new_document_path.unlink(missing_ok=True)
        raise


def _resolve_subject(
    db: Session,
    payload: ExternalImportPayload,
    subject_id: str | None,
) -> Subject:
    subject: Subject | None = None
    if subject_id:
        subject = db.get(Subject, subject_id)
        if subject is None:
            raise DomainError(404, "subject_not_found", "所选学科不存在")
        return subject
    if payload.subject.id:
        subject = db.get(Subject, payload.subject.id)
    if subject is None and payload.subject.name.strip():
        subject = db.scalar(
            select(Subject).where(
                func.lower(Subject.name) == payload.subject.name.strip().lower()
            )
        )
    if subject is None:
        raise DomainError(
            422,
            "subject_not_found",
            "JSON 中的学科不存在，请在导入页选择一个已有学科",
        )
    return subject


def _store_external_document(
    db: Session,
    data: bytes,
    payload: ExternalImportPayload,
    subject: Subject,
    original_name: str,
    digest: str,
    settings: Settings,
) -> tuple[Document, Path]:
    root = settings.resolved(Path(settings.upload_dir))
    root.mkdir(parents=True, exist_ok=True)
    document_id = str(uuid4())
    storage_name = f"{document_id}.json"
    path = (root / storage_name).resolve()
    if root != path.parent and root not in path.parents:
        raise DomainError(500, "unsafe_storage_path", "资料存储路径不安全")
    path.write_bytes(data)
    try:
        content_title = payload.document.name.strip()[:300] or Path(original_name).stem
        page_values = [
            point.source.page
            for point in payload.knowledge_points
            if point.source.page
        ]
        document = Document(
            id=document_id,
            subject_id=subject.id,
            chapter_id=None,
            name=(payload.document.name.strip() or Path(original_name).stem)[:240],
            content_title=content_title,
            original_filename=original_name,
            storage_name=storage_name,
            mime_type="application/json",
            extension=".json",
            size_bytes=len(data),
            sha256=digest,
            status="parsed",
            page_count=max(page_values) if page_values else None,
            parsed_at=utc_now(),
        )
        db.add(document)
        db.flush()
        return document, path
    except Exception:
        path.unlink(missing_ok=True)
        raise


def rebuild_external_preview(db: Session, job: ImportJob) -> ImportRead:
    if not job.payload:
        raise DomainError(409, "external_payload_missing", "导入任务缺少原始 JSON 数据")
    payload = ExternalImportPayload.model_validate(job.payload)
    document = db.get(Document, job.document_id)
    if document is None:
        raise DomainError(404, "document_not_found", "导入资料不存在")
    subject = _resolve_subject(db, payload, document.subject_id)
    suggestion = build_external_suggestion(
        db,
        document,
        payload,
        subject,
        duplicate_import=bool(job.suggestion and job.suggestion.get("duplicate_import")),
    )
    job.suggestion = suggestion.model_dump()
    job.status = "awaiting_confirmation"
    job.stage = "外部 AI JSON 已校验，等待确认归档"
    job.progress = 50
    job.error = None
    job.finished_at = None
    db.commit()
    db.refresh(job)
    return import_service._import_read(db, job)


def confirm_external_import(
    db: Session,
    import_id: str,
    payload: ImportConfirmRequest,
    *,
    settings: Settings | None = None,
) -> ImportRead:
    job = import_service.get_import(db, import_id)
    if job.source_type != "external_json":
        raise DomainError(409, "not_external_import", "该任务不是外部 AI JSON 导入")
    if job.status not in {"awaiting_confirmation", "failed"}:
        raise DomainError(409, "import_not_confirmable", "当前导入任务不需要确认")
    if not job.payload:
        raise DomainError(409, "external_payload_missing", "导入任务缺少原始 JSON 数据")
    external = ExternalImportPayload.model_validate(job.payload)
    document = db.get(Document, job.document_id)
    if document is None:
        raise DomainError(404, "document_not_found", "导入资料不存在")

    subject = _resolve_subject(db, external, payload.subject_id)
    strategy = job.duplicate_strategy or "skip"

    created_chapter_ids: list[str] = []
    reused_chapter_ids: list[str] = []
    resolved: list[str | None] = []
    root_id: str | None = None
    suggestion: ImportSuggestion | None = None
    path_chapter: dict[tuple[str, ...], str | None] = {}

    if payload.accept_suggestions:
        suggestion = build_external_suggestion(db, document, external, subject)
        created_chapter_ids, reused_chapter_ids, resolved, root_id = (
            import_service._resolve_suggestion_chapters(
                db,
                document,
                job,
                subject,
                suggestion,
                create_missing=payload.create_missing,
            )
        )
        nodes_paths = _node_paths(suggestion.chapters)
        path_chapter = {
            path: resolved[index] if index < len(resolved) else None
            for index, path in enumerate(nodes_paths)
        }
        for index, path in enumerate(nodes_paths):
            if len(path) > 1:
                path_chapter.setdefault(path[1:], resolved[index])
    else:
        chapter_id = payload.chapter_id
        chapter = db.get(Chapter, chapter_id) if chapter_id else None
        if chapter is not None and chapter.subject_id != subject.id:
            raise DomainError(
                422,
                "chapter_subject_mismatch",
                "所选章节不属于该学科",
            )
        root_id = chapter.id if chapter else None

    existing_points = db.scalars(
        select(KnowledgePoint).where(KnowledgePoint.subject_id == subject.id)
    ).all()
    by_chapter_name = {
        (point.chapter_id, normalize_name(point.name)): point
        for point in existing_points
    }
    by_document_name = {
        (point.document_id, normalize_name(point.name)): point
        for point in existing_points
    }
    seen_external_ids: set[str] = set()
    created_points = 0
    updated_points = 0
    skipped_points = 0

    for point in external.knowledge_points:
        path = tuple(normalize_name(part) for part in point.chapter_path if part.strip())
        target_chapter_id = (
            path_chapter.get(path)
            or path_chapter.get(path[1:] if len(path) > 1 else path)
            or root_id
        )
        normalized_title = normalize_name(point.title)
        existing = by_chapter_name.get((target_chapter_id, normalized_title))
        if existing is None:
            existing = by_document_name.get((document.id, normalized_title))
        if point.point_id:
            if point.point_id in seen_external_ids:
                skipped_points += 1
                continue
            seen_external_ids.add(point.point_id)

        point_type, category_warning = _category(point.category)
        importance, importance_warning = _importance(point.importance)
        warnings = [
            warning
            for warning in (category_warning, importance_warning)
            if warning
        ]
        if not point.source.page and not point.source.slide and not point.source.locator:
            warnings.append("外部 AI 未提供来源页码/幻灯片")
        warnings.append("外部 AI 导入，来源未与原文自动核验")

        if existing is not None:
            can_update = (
                strategy == "update_pending"
                and existing.review_status == ReviewStatus.PENDING.value
                and existing.origin == KnowledgeOrigin.AI.value
                and existing.document_id == document.id
            )
            if not can_update:
                skipped_points += 1
                continue
            existing.name = point.title.strip()[:300]
            existing.point_type = point_type
            existing.explanation = point.content.strip()
            existing.core_points = list(point.key_terms)
            existing.importance = importance
            existing.prerequisites = list(point.prerequisites)
            existing.external_id = point.point_id
            existing.review_note = "；".join(warnings)
            existing.needs_review = True
            updated_points += 1
            continue

        knowledge_point = KnowledgePoint(
            subject_id=subject.id,
            chapter_id=target_chapter_id,
            document_id=document.id,
            name=point.title.strip()[:300],
            point_type=point_type,
            explanation=point.content.strip(),
            core_points=list(point.key_terms),
            conditions=None,
            source_quote=point.source.quote,
            source_quote_verified=False,
            source_page=point.source.page,
            source_page_end=point.source.page_end,
            source_slide=point.source.slide,
            source_locator=_source_locator(point),
            source_chunk_id=None,
            importance=importance,
            prerequisites=list(point.prerequisites),
            external_id=point.point_id,
            confidence=point.confidence,
            review_note="；".join(warnings),
            needs_review=True,
            origin=KnowledgeOrigin.AI.value,
            review_status=ReviewStatus.PENDING.value,
        )
        db.add(knowledge_point)
        created_points += 1

    document.subject_id = subject.id
    document.chapter_id = root_id
    chapter = db.get(Chapter, root_id) if root_id else None
    job.result = ImportResult(
        subject_id=subject.id,
        chapter_id=root_id,
        chapter_name=chapter.name if chapter else None,
        created_chapter_ids=created_chapter_ids,
        reused_chapter_ids=reused_chapter_ids,
        chapter_path=(
            import_service._chapter_path(db, chapter).split(" > ")
            if chapter
            else []
        ),
        duplicate=False,
        knowledge_point_count=len(external.knowledge_points),
        created_point_count=created_points,
        updated_point_count=updated_points,
        skipped_point_count=skipped_points,
        warning_count=(
            suggestion.duplicate_point_count if suggestion is not None else 0
        ),
    ).model_dump()
    job.status = "completed"
    job.stage = "外部 AI 知识点已导入，等待人工审核"
    job.progress = 100
    job.analysis_status = "not_started"
    job.error = None
    job.finished_at = utc_now()
    db.commit()
    db.refresh(job)
    return import_service._import_read(db, job)


def external_template() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "json_schema": external_json_schema(),
        "prompt": build_external_prompt(),
        "example": EXTERNAL_IMPORT_EXAMPLE,
    }
