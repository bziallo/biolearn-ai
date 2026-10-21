from __future__ import annotations

import logging
import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.enums import JobStatus
from app.core.errors import DomainError
from app.db.base import utc_now
from app.db.session import SessionLocal
from app.models import (
    Chapter,
    Document,
    DocumentChunk,
    ImportJob,
    ImportPreferences,
    KnowledgeExtractionJob,
    KnowledgePoint,
    Subject,
)
from app.schemas.imports import (
    ImportConfirmRequest,
    ImportPreferencesRead,
    ImportPreferencesUpdate,
    ImportRead,
    ImportResult,
    ImportSuggestion,
    SuggestedChapter,
)
from app.services import documents as document_service
from app.services import knowledge as knowledge_service
from app.services.knowledge_common import normalize_name
from app.services.mappers import job_read

IMPORT_MODES = {"preset", "auto_create", "smart_archive"}
logger = logging.getLogger(__name__)
UNCERTAIN_POLICIES = {"confirm", "use_default", "create"}
RUNNING_STATUSES = {"queued", "parsing", "detecting", "archiving", "analyzing"}
MAX_SUGGESTED_CHAPTERS = 40

_NUMBERED_CHAPTER = re.compile(
    r"^\s*(?:第\s*[一二三四五六七八九十百0-9]+\s*[章节篇部]"
    r"|[0-9]+(?:\.[0-9]+){0,3}[、.．\s]"
    r"|[一二三四五六七八九十]+\s*[、.．]"
    r"|[（(]\s*[一二三四五六七八九十0-9]+\s*[）)])"
)
_TITLE_NUMBER = re.compile(r"^\s*(第\s*[一二三四五六七八九十百0-9]+\s*[章节篇部])")
_TITLE_DECIMAL = re.compile(r"^\s*([0-9]+(?:\.[0-9]+){1,3})")
_TITLE_CN = re.compile(r"^\s*([一二三四五六七八九十]+)\s*[、.．]")
_TITLE_PAREN = re.compile(r"^\s*[（(]\s*([一二三四五六七八九十0-9]+)\s*[）)]")
_TOC_MARKERS = re.compile(r"(目录|目\s*录|contents)", re.IGNORECASE)


@dataclass(slots=True)
class OutlineItem:
    name: str
    level: int
    source_slide: int | None
    source_kind: str
    confidence: float


# ---------------------------------------------------------------------------
# Preferences


def _preferences_model(db: Session) -> ImportPreferences | None:
    return db.get(ImportPreferences, 1)


def preferences_read(
    db: Session,
    preferences: ImportPreferences | None = None,
) -> ImportPreferencesRead:
    current = preferences or _preferences_model(db)
    subject = (
        db.get(Subject, current.default_subject_id)
        if current is not None and current.default_subject_id
        else None
    )
    chapter = (
        db.get(Chapter, current.default_chapter_id)
        if current is not None and current.default_chapter_id
        else None
    )
    if subject is None or chapter is None or chapter.subject_id != subject.id:
        chapter = None
    return ImportPreferencesRead(
        default_subject_id=subject.id if subject else None,
        default_subject_name=subject.name if subject else None,
        default_chapter_id=chapter.id if chapter else None,
        default_chapter_name=chapter.name if chapter else None,
        default_mode=current.default_mode if current else "preset",
        auto_analyze=current.auto_analyze if current else True,
        require_preview=current.require_preview if current else True,
        uncertain_policy=current.uncertain_policy if current else "confirm",
        updated_at=current.updated_at if current else None,
    )


def save_preferences(
    db: Session,
    payload: ImportPreferencesUpdate,
) -> ImportPreferencesRead:
    subject: Subject | None = None
    chapter: Chapter | None = None
    if payload.default_subject_id:
        subject = db.get(Subject, payload.default_subject_id)
        if subject is None:
            raise DomainError(404, "subject_not_found", "默认学科不存在")
    if payload.default_chapter_id:
        if subject is None:
            raise DomainError(
                422,
                "default_subject_required",
                "设置默认章节前必须先设置默认学科",
            )
        chapter = db.get(Chapter, payload.default_chapter_id)
        if chapter is None:
            raise DomainError(404, "chapter_not_found", "默认章节不存在")
        if chapter.subject_id != subject.id:
            raise DomainError(
                422,
                "chapter_subject_mismatch",
                "默认章节不属于默认学科",
            )

    current = _preferences_model(db)
    if current is None:
        current = ImportPreferences(id=1)
        db.add(current)
    current.default_subject_id = subject.id if subject else None
    current.default_chapter_id = chapter.id if chapter else None
    current.default_mode = payload.default_mode
    current.auto_analyze = payload.auto_analyze
    current.require_preview = payload.require_preview
    current.uncertain_policy = payload.uncertain_policy
    db.commit()
    db.refresh(current)
    return preferences_read(db, current)


def resolve_options(
    db: Session,
    *,
    mode: str | None,
    auto_analyze: bool | None,
    require_preview: bool | None,
    uncertain_policy: str | None,
) -> tuple[str, bool, bool, str, ImportPreferences | None]:
    prefs = _preferences_model(db)
    resolved_mode = mode or (prefs.default_mode if prefs else "preset")
    if resolved_mode not in IMPORT_MODES:
        raise DomainError(422, "invalid_import_mode", "不支持的导入模式")
    resolved_policy = uncertain_policy or (
        prefs.uncertain_policy if prefs else "confirm"
    )
    if resolved_policy not in UNCERTAIN_POLICIES:
        raise DomainError(422, "invalid_uncertain_policy", "不支持的归档不确定策略")
    return (
        resolved_mode,
        auto_analyze if auto_analyze is not None else (prefs.auto_analyze if prefs else True),
        require_preview
        if require_preview is not None
        else (prefs.require_preview if prefs else True),
        resolved_policy,
        prefs,
    )


# ---------------------------------------------------------------------------
# Structure detection


def _clean_line(value: str) -> str:
    line = value.strip()
    if "|" in line:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        line = next(
            (
                cell
                for cell in cells
                if cell and not re.fullmatch(r"[-: ]+", cell)
            ),
            "",
        )
    line = re.sub(r"^[#>*\-•·\s]+", "", line)
    line = re.sub(r"^[0-9]+[）)]\s*", "", line)
    return line.strip(" \t；;，,。.")


def _line_level(line: str) -> int | None:
    if _TITLE_NUMBER.match(line):
        return 1 if "章" in line[:8] or "篇" in line[:8] or "部" in line[:8] else 2
    decimal = _TITLE_DECIMAL.match(line)
    if decimal:
        return min(3, decimal.group(1).count(".") + 1)
    if _TITLE_CN.match(line):
        return 1
    if _TITLE_PAREN.match(line):
        return 2
    return None


def _outline_from_toc(
    chunks: list[DocumentChunk],
) -> tuple[list[OutlineItem], int | None]:
    slides: dict[int, list[DocumentChunk]] = defaultdict(list)
    for chunk in chunks:
        if chunk.slide_number is not None:
            slides[chunk.slide_number].append(chunk)
    for slide_number in sorted(slides):
        slide_chunks = slides[slide_number]
        text = "\n".join(chunk.content for chunk in slide_chunks)
        title = _slide_title(slide_chunks) or ""
        if not (_TOC_MARKERS.search(title) or _TOC_MARKERS.search(text[:200])):
            continue
        items: list[OutlineItem] = []
        seen: set[str] = set()
        for raw in re.split(r"[\n\r；;]+", text):
            line = _clean_line(raw)
            if not line or _TOC_MARKERS.search(line):
                continue
            if line in {"章节", "内容", "标题", "页码", "序号", "名称", "章节名称"}:
                continue
            if len(line) < 2 or len(line) > 100:
                continue
            if re.fullmatch(r"[0-9\s/.-]+", line):
                continue
            level = _line_level(line) or 1
            key = normalize_name(line)
            if not key or key in seen:
                continue
            seen.add(key)
            items.append(
                OutlineItem(
                    name=line[:160],
                    level=level,
                    source_slide=slide_number,
                    source_kind="toc",
                    confidence=0.9,
                )
            )
            if len(items) >= MAX_SUGGESTED_CHAPTERS:
                break
        if len(items) >= 2:
            return items, slide_number
    return [], None


def _slide_title(chunks: list[DocumentChunk]) -> str | None:
    for chunk in chunks:
        if chunk.heading_path:
            parts = [part.strip() for part in chunk.heading_path.split(">") if part.strip()]
            if parts:
                return parts[-1]
        if chunk.heading_level:
            first = chunk.content.splitlines()[0].strip()
            if first:
                return first
    return None


def _numbered_slide_titles(chunks: list[DocumentChunk]) -> list[OutlineItem]:
    slides: dict[int, list[DocumentChunk]] = defaultdict(list)
    for chunk in chunks:
        if chunk.slide_number is not None:
            slides[chunk.slide_number].append(chunk)
    items: list[OutlineItem] = []
    seen: set[str] = set()
    for slide_number in sorted(slides):
        title = _slide_title(slides[slide_number])
        if not title:
            continue
        level = _line_level(title)
        if level is None:
            continue
        key = normalize_name(title)
        if not key or key in seen:
            continue
        seen.add(key)
        items.append(
            OutlineItem(
                name=title[:160],
                level=level,
                source_slide=slide_number,
                source_kind="slide_title",
                confidence=0.78,
            )
        )
        if len(items) >= MAX_SUGGESTED_CHAPTERS:
            break
    return items


def _heading_items(chunks: list[DocumentChunk]) -> list[OutlineItem]:
    items: list[OutlineItem] = []
    seen: set[str] = set()
    for chunk in chunks:
        if not chunk.heading_path:
            continue
        parts = [part.strip() for part in chunk.heading_path.split(">") if part.strip()]
        if not parts:
            continue
        name = parts[-1]
        level = chunk.heading_level or len(parts)
        key = normalize_name(name)
        if not key or key in seen:
            continue
        seen.add(key)
        items.append(
            OutlineItem(
                name=name[:160],
                level=max(1, min(level, 6)),
                source_slide=chunk.slide_number,
                source_kind="heading",
                confidence=0.72,
            )
        )
        if len(items) >= MAX_SUGGESTED_CHAPTERS:
            break
    return items


def build_outline(
    document: Document,
    chunks: list[DocumentChunk],
) -> tuple[list[SuggestedChapter], str, float, list[str]]:
    title = (document.content_title or Path(document.original_filename).stem or document.name).strip()
    title = title[:160] or "未命名资料"
    root_key = normalize_name(title)
    reasons: list[str] = []

    toc_items, toc_slide = _outline_from_toc(chunks)
    if toc_items:
        source = "toc"
        confidence = 0.9
        reasons.append(f"检测到目录页（第 {toc_slide} 张幻灯片）")
        candidates = toc_items
    else:
        numbered = _numbered_slide_titles(chunks)
        if numbered:
            source = "slide_titles"
            confidence = 0.78
            reasons.append("未检测到目录页，按带编号的幻灯片标题生成章节建议")
            candidates = numbered
        else:
            # PPT slide titles are not automatically chapter headings. If
            # there is no TOC and no numbering, only reuse explicit document
            # headings (DOCX/Markdown); otherwise keep a single root chapter.
            has_slides = document.extension == ".pptx" or any(
                chunk.slide_number is not None for chunk in chunks
            )
            headings = [] if has_slides else _heading_items(chunks)
            if headings:
                source = "headings"
                confidence = 0.7
                reasons.append("按文档标题结构生成章节建议")
                candidates = headings
            else:
                source = "filename"
                confidence = 0.35
                reasons.append("未检测到明确目录或编号标题，仅建议归入资料标题章节")
                candidates = []

    nodes: list[SuggestedChapter] = [
        SuggestedChapter(
            name=title,
            level=1,
            parent_index=None,
            action="create",
            confidence=confidence,
            source_slide=None,
            source_kind="document_title",
            reason="资料标题",
        )
    ]
    stack: list[tuple[int, int]] = [(1, 0)]
    seen: set[tuple[int, str]] = set()

    for item in candidates:
        key = normalize_name(item.name)
        if not key or key == root_key:
            continue
        while stack and stack[-1][0] >= item.level:
            stack.pop()
        parent_index = stack[-1][1] if stack else 0
        dedupe_key = (parent_index, key)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        index = len(nodes)
        nodes.append(
            SuggestedChapter(
                name=item.name[:160],
                level=min(item.level, 6),
                parent_index=parent_index,
                action="create",
                confidence=item.confidence,
                source_slide=item.source_slide,
                source_kind=item.source_kind,
                reason="来自目录" if item.source_kind == "toc" else "来自幻灯片/标题结构",
            )
        )
        stack.append((item.level, index))
        if len(nodes) >= MAX_SUGGESTED_CHAPTERS:
            break

    if len(nodes) == 1:
        reasons.append("只生成一个资料标题章节，避免凭空创建大量章节")
    return nodes, source, confidence, reasons


# ---------------------------------------------------------------------------
# Matching and archiving


def _chapter_path(db: Session, chapter: Chapter) -> str:
    names: list[str] = []
    current: Chapter | None = chapter
    seen: set[str] = set()
    while current is not None and current.id not in seen:
        seen.add(current.id)
        names.append(current.name)
        current = db.get(Chapter, current.parent_id) if current.parent_id else None
    return " > ".join(reversed(names))


def _subject_match(
    db: Session,
    text: str,
    subject: Subject,
) -> tuple[float, str]:
    normalized = normalize_name(text)
    if not normalized:
        return 0.5, "使用导入时选择的学科"
    if normalize_name(subject.name) in normalized:
        return 0.95, "文件名或标题包含学科名称"
    best = max(
        (
            SequenceMatcher(None, normalized, normalize_name(candidate.name)).ratio()
            for candidate in db.scalars(select(Subject)).all()
        ),
        default=0.0,
    )
    if best >= 0.6:
        return min(0.8, best), "文件名或标题与现有学科名称相近"
    return 0.55, "使用导入时选择的学科"


def _match_chapters(
    db: Session,
    subject: Subject,
    nodes: list[SuggestedChapter],
) -> ImportSuggestion:
    chapters = db.scalars(
        select(Chapter).where(Chapter.subject_id == subject.id)
    ).all()
    by_parent: dict[tuple[str | None, str], Chapter] = {}
    by_name: dict[str, list[Chapter]] = defaultdict(list)
    for chapter in chapters:
        key = normalize_name(chapter.name)
        by_parent[(chapter.parent_id, key)] = chapter
        by_name[key].append(chapter)

    resolved: list[str | None] = [None] * len(nodes)
    for index, node in enumerate(nodes):
        parent_id = (
            None
            if node.parent_index is None
            else resolved[node.parent_index]
        )
        key = normalize_name(node.name)
        exact = by_parent.get((parent_id, key)) if key else None
        if exact is not None:
            node.action = "reuse"
            node.existing_chapter_id = exact.id
            node.existing_path = _chapter_path(db, exact)
            node.reason = "同名章节已存在于目标父级"
            resolved[index] = exact.id
            continue

        same_name = by_name.get(key, []) if key else []
        if same_name:
            node.action = "uncertain"
            node.existing_chapter_id = same_name[0].id
            node.existing_path = _chapter_path(db, same_name[0])
            node.reason = "同名章节已存在，但父级不同；为避免重复，建议复用或确认"
            resolved[index] = same_name[0].id
            continue

        best: tuple[float, Chapter | None] = (0.0, None)
        for candidate in chapters:
            ratio = SequenceMatcher(
                None,
                key,
                normalize_name(candidate.name),
            ).ratio()
            if ratio > best[0]:
                best = (ratio, candidate)
        if best[1] is not None and best[0] >= 0.86:
            node.action = "uncertain"
            node.existing_chapter_id = best[1].id
            node.existing_path = _chapter_path(db, best[1])
            node.reason = f"发现相似章节（相似度 {best[0]:.0%}），避免重复创建"
            resolved[index] = best[1].id
            continue

        node.action = "create"
        node.existing_chapter_id = None
        node.existing_path = None
        node.reason = "未找到匹配章节"
        resolved[index] = None

    source_confidence = nodes[0].confidence if nodes else 0.35
    needs_confirmation = any(node.action == "uncertain" for node in nodes)
    reasons: list[str] = []
    if any(node.action == "uncertain" for node in nodes):
        reasons.append("存在同名或相似章节，需要确认是否复用")
    if any(node.action == "create" for node in nodes):
        reasons.append("需要创建缺失章节")
    text = f"{subject.name} {nodes[0].name if nodes else ''}"
    subject_confidence, subject_reason = _subject_match(db, text, subject)
    return ImportSuggestion(
        title=nodes[0].name if nodes else "未命名资料",
        subject_id=subject.id,
        subject_name=subject.name,
        subject_confidence=subject_confidence,
        subject_reason=subject_reason,
        outline_source="heuristic",
        chapters=nodes,
        confidence=source_confidence,
        needs_confirmation=needs_confirmation,
        reasons=reasons,
    )


def detect_structure(
    db: Session,
    document: Document,
    chunks: list[DocumentChunk],
) -> ImportSuggestion:
    subject = db.get(Subject, document.subject_id)
    if subject is None:
        raise DomainError(409, "subject_missing", "资料所属学科不存在")
    nodes, source, _, reasons = build_outline(document, chunks)
    suggestion = _match_chapters(db, subject, nodes)
    suggestion.outline_source = source
    suggestion.reasons = [*reasons, *suggestion.reasons]
    return suggestion


def _next_sort_order(
    db: Session,
    subject_id: str,
    parent_id: str | None,
) -> int:
    conditions = [Chapter.subject_id == subject_id]
    if parent_id is None:
        conditions.append(Chapter.parent_id.is_(None))
    else:
        conditions.append(Chapter.parent_id == parent_id)
    current = db.scalar(select(func.max(Chapter.sort_order)).where(*conditions))
    return 0 if current is None else current + 10


def _resolve_suggestion_chapters(
    db: Session,
    document: Document,
    import_job: ImportJob,
    subject: Subject,
    suggestion: ImportSuggestion,
    *,
    create_missing: bool,
) -> tuple[list[str], list[str], list[str | None], str | None]:
    created_ids: list[str] = []
    reused_ids: list[str] = []
    resolved: list[str | None] = [None] * len(suggestion.chapters)

    for index, node in enumerate(suggestion.chapters):
        parent_id = (
            None
            if node.parent_index is None
            else resolved[node.parent_index]
        )
        parent = db.get(Chapter, parent_id) if parent_id else None
        if parent is not None and parent.subject_id != subject.id:
            raise DomainError(
                422,
                "chapter_subject_mismatch",
                "自动建章时父章节不属于目标学科",
            )

        existing: Chapter | None = None
        if node.existing_chapter_id:
            candidate = db.get(Chapter, node.existing_chapter_id)
            if candidate is not None and candidate.subject_id == subject.id:
                existing = candidate
        if existing is None:
            key = normalize_name(node.name)
            if key:
                conditions = [
                    Chapter.subject_id == subject.id,
                    Chapter.name == node.name,
                ]
                if parent_id is None:
                    conditions.append(Chapter.parent_id.is_(None))
                else:
                    conditions.append(Chapter.parent_id == parent_id)
                existing = db.scalar(select(Chapter).where(*conditions))

        if existing is not None:
            resolved[index] = existing.id
            reused_ids.append(existing.id)
            continue

        if not create_missing:
            raise DomainError(
                409,
                "chapter_confirmation_required",
                "该导入包含需要创建的章节，请先确认章节预览",
            )

        chapter = Chapter(
            subject_id=subject.id,
            parent_id=parent_id,
            name=node.name[:160],
            description="",
            sort_order=_next_sort_order(db, subject.id, parent_id),
            source_document_id=document.id,
            source_import_job_id=import_job.id,
            source_slide=node.source_slide,
        )
        db.add(chapter)
        db.flush()
        resolved[index] = chapter.id
        created_ids.append(chapter.id)

    root_id = resolved[0] if resolved else None
    if not suggestion.chapters:
        root_id = db.scalar(
            select(Chapter.id).where(
                Chapter.subject_id == subject.id,
                Chapter.parent_id.is_(None),
                Chapter.name == suggestion.title,
            )
        )
        if root_id is None:
            if not create_missing:
                raise DomainError(
                    409,
                    "chapter_confirmation_required",
                    "该导入需要创建一个资料章节，请先确认",
                )
            chapter = Chapter(
                subject_id=subject.id,
                parent_id=None,
                name=suggestion.title[:160],
                description="",
                sort_order=_next_sort_order(db, subject.id, None),
                source_document_id=document.id,
                source_import_job_id=import_job.id,
            )
            db.add(chapter)
            db.flush()
            root_id = chapter.id
            created_ids.append(chapter.id)

    return created_ids, reused_ids, resolved, root_id


def archive_suggestion(
    db: Session,
    document: Document,
    import_job: ImportJob,
    subject: Subject,
    suggestion: ImportSuggestion,
    *,
    create_missing: bool,
) -> ImportResult:
    """Resolve the suggested tree and assign the document, in one transaction."""

    created_ids, reused_ids, _, root_id = _resolve_suggestion_chapters(
        db,
        document,
        import_job,
        subject,
        suggestion,
        create_missing=create_missing,
    )

    document.subject_id = subject.id
    document.chapter_id = root_id
    db.execute(
        KnowledgePoint.__table__.update()
        .where(KnowledgePoint.document_id == document.id)
        .values(subject_id=subject.id, chapter_id=root_id)
    )
    root = db.get(Chapter, root_id) if root_id else None
    result = ImportResult(
        subject_id=subject.id,
        chapter_id=root_id,
        chapter_name=root.name if root else None,
        created_chapter_ids=created_ids,
        reused_chapter_ids=reused_ids,
        chapter_path=(
            _chapter_path(db, root).split(" > ") if root else []
        ),
        duplicate=False,
    )
    db.commit()
    return result


# ---------------------------------------------------------------------------
# Import job lifecycle


def _import_read(db: Session, job: ImportJob) -> ImportRead:
    document = db.get(Document, job.document_id)
    suggestion = (
        ImportSuggestion.model_validate(job.suggestion)
        if job.suggestion
        else None
    )
    result = ImportResult.model_validate(job.result) if job.result else None
    return ImportRead(
        id=job.id,
        document_id=job.document_id,
        document_name=document.name if document else "",
        document_status=document.status if document else "missing",
        status=job.status,
        stage=job.stage,
        progress=job.progress,
        mode=job.mode,  # type: ignore[arg-type]
        source_type=job.source_type,
        duplicate_strategy=job.duplicate_strategy,
        auto_analyze=job.auto_analyze,
        require_preview=job.require_preview,
        uncertain_policy=job.uncertain_policy,  # type: ignore[arg-type]
        suggestion=suggestion,
        result=result,
        error=job.error,
        analysis_job_id=job.analysis_job_id,
        analysis_status=job.analysis_status,
        analysis_error=job.analysis_error,
        timings=job.timings,
        created_at=job.created_at,
        updated_at=job.updated_at,
        finished_at=job.finished_at,
    )


def get_import(db: Session, import_id: str) -> ImportJob:
    job = db.get(ImportJob, import_id)
    if job is None:
        raise DomainError(404, "import_not_found", "导入任务不存在")
    return job


def get_import_read(db: Session, import_id: str) -> ImportRead:
    return _import_read(db, get_import(db, import_id))


def list_imports(db: Session, limit: int = 20) -> list[ImportRead]:
    jobs = db.scalars(
        select(ImportJob)
        .order_by(ImportJob.created_at.desc())
        .limit(max(1, min(limit, 100)))
    ).all()
    return [_import_read(db, job) for job in jobs]


def _set_stage(
    db: Session,
    job: ImportJob,
    status: str,
    stage: str,
    progress: int,
    *,
    commit: bool = True,
) -> None:
    job.status = status
    job.stage = stage
    job.progress = progress
    if commit:
        db.commit()


def _fail_import(db: Session, job: ImportJob, message: str) -> None:
    job.status = "failed"
    job.stage = "导入失败"
    job.error = message
    job.finished_at = utc_now()
    db.commit()


async def create_import(
    db: Session,
    upload: UploadFile,
    *,
    subject_id: str | None,
    chapter_id: str | None,
    name: str | None,
    mode: str | None,
    auto_analyze: bool | None,
    require_preview: bool | None,
    uncertain_policy: str | None,
    settings: Settings | None = None,
) -> ImportRead:
    current_settings = settings or get_settings()
    resolved_mode, resolved_auto, resolved_preview, resolved_policy, prefs = (
        resolve_options(
            db,
            mode=mode,
            auto_analyze=auto_analyze,
            require_preview=require_preview,
            uncertain_policy=uncertain_policy,
        )
    )
    resolved_subject_id = subject_id or (
        prefs.default_subject_id if prefs else None
    )
    if not resolved_subject_id:
        raise DomainError(
            422,
            "default_subject_missing",
            "请先设置默认学科，或在导入时选择学科",
        )
    subject = db.get(Subject, resolved_subject_id)
    if subject is None:
        raise DomainError(404, "subject_not_found", "学科不存在")

    resolved_chapter_id = chapter_id or (
        prefs.default_chapter_id if prefs and resolved_mode == "preset" else None
    )
    if resolved_chapter_id:
        chapter = db.get(Chapter, resolved_chapter_id)
        if chapter is None:
            raise DomainError(404, "chapter_not_found", "章节不存在")
        if chapter.subject_id != subject.id:
            raise DomainError(
                422,
                "chapter_subject_mismatch",
                "所选章节不属于该学科",
            )

    document = await document_service.create_document_from_upload(
        db,
        upload,
        subject_id=subject.id,
        chapter_id=resolved_chapter_id if resolved_mode == "preset" else None,
        name=name,
        force=False,
        settings=current_settings,
        dedupe_subject=True,
        return_existing=True,
    )

    if document.duplicate:
        job = ImportJob(
            document_id=document.id,
            status="completed",
            stage="文件已存在，未重复导入或重复建章",
            progress=100,
            mode=resolved_mode,
            auto_analyze=False,
            require_preview=resolved_preview,
            uncertain_policy=resolved_policy,
            result=ImportResult(
                subject_id=document.subject_id,
                chapter_id=document.chapter_id,
                chapter_name=document.chapter_name,
                duplicate=True,
                chapter_path=[document.chapter_name] if document.chapter_name else [],
            ).model_dump(),
            finished_at=utc_now(),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return _import_read(db, job)

    job = ImportJob(
        document_id=document.id,
        status="queued",
        stage="等待解析",
        progress=0,
        mode=resolved_mode,
        auto_analyze=resolved_auto,
        require_preview=resolved_preview,
        uncertain_policy=resolved_policy,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _import_read(db, job)


def _load_chunks(db: Session, document_id: str) -> list[DocumentChunk]:
    return list(
        db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        ).all()
    )


def _start_analysis(
    db: Session,
    import_job: ImportJob,
    document: Document,
    settings: Settings,
) -> bool:
    try:
        job = knowledge_service.create_extraction_job(
            db,
            document.id,
            settings=settings,
        )
    except DomainError as exc:
        import_job.analysis_status = "failed"
        import_job.analysis_error = exc.message
        import_job.status = "completed"
        import_job.stage = "资料已归档；AI 分析未启动"
        import_job.progress = 100
        import_job.finished_at = utc_now()
        db.commit()
        return False
    import_job.analysis_job_id = job.id
    import_job.analysis_status = "running"
    import_job.status = "analyzing"
    import_job.stage = "资料已归档，AI 知识点分析中"
    import_job.progress = 90
    db.commit()
    return True


def _finish_analysis(
    db: Session,
    import_job: ImportJob,
    analysis_job: KnowledgeExtractionJob | None,
) -> None:
    if analysis_job is None:
        import_job.analysis_status = "failed"
        import_job.analysis_error = "AI 任务不存在"
    elif analysis_job.status == JobStatus.COMPLETED.value:
        import_job.analysis_status = "completed"
        import_job.stage = "资料已归档，AI 知识点草稿已生成"
    elif analysis_job.status == JobStatus.CANCELLED.value:
        import_job.analysis_status = "cancelled"
        import_job.stage = "资料已归档，AI 分析已停止"
    else:
        import_job.analysis_status = "failed"
        import_job.analysis_error = analysis_job.error or "AI 分析失败"
        import_job.stage = "资料已归档，AI 分析失败"
    import_job.status = "completed"
    import_job.progress = 100
    import_job.finished_at = utc_now()
    db.commit()


def run_import(
    import_id: str,
    *,
    session_factory: Callable[[], Session] = SessionLocal,
    settings: Settings | None = None,
    client: Any | None = None,
) -> None:
    current_settings = settings or get_settings()
    analysis_id: str | None = None
    with session_factory() as db:
        job = db.get(ImportJob, import_id)
        if job is None:
            return
        try:
            document = db.get(Document, job.document_id)
            if document is None:
                _fail_import(db, job, "资料不存在")
                return

            if document.status != "parsed":
                _set_stage(db, job, "parsing", "解析文件", 10)
                document_service.process_document(
                    document.id,
                    session_factory=session_factory,
                    settings=current_settings,
                )
                db.expire_all()
                document = db.get(Document, job.document_id)
                job = db.get(ImportJob, import_id)
                if document is None or job is None:
                    return
                if document.status != "parsed":
                    _fail_import(
                        db,
                        job,
                        document.parse_error or "文件解析失败",
                    )
                    return

            if job.mode == "preset":
                chapter = (
                    db.get(Chapter, document.chapter_id)
                    if document.chapter_id
                    else None
                )
                _set_stage(db, job, "archiving", "保存资料归档", 60)
                if chapter is not None:
                    document.chapter_id = chapter.id
                job.result = ImportResult(
                    subject_id=document.subject_id,
                    chapter_id=document.chapter_id,
                    chapter_name=chapter.name if chapter else None,
                    chapter_path=[chapter.name] if chapter else [],
                ).model_dump()
                db.commit()
            else:
                _set_stage(db, job, "detecting", "识别章节结构", 35)
                chunks = _load_chunks(db, document.id)
                suggestion = detect_structure(db, document, chunks)
                job.suggestion = suggestion.model_dump()
                db.commit()
                needs_creation = any(
                    chapter.action == "create"
                    for chapter in suggestion.chapters
                )
                if (
                    (job.require_preview and needs_creation)
                    or (
                        suggestion.needs_confirmation
                        and job.uncertain_policy == "confirm"
                    )
                ):
                    job.status = "awaiting_confirmation"
                    job.stage = "等待确认归档结构"
                    job.progress = 50
                    job.finished_at = None
                    db.commit()
                    return

                if (
                    suggestion.needs_confirmation
                    and job.uncertain_policy == "use_default"
                ):
                    preferences = _preferences_model(db)
                    default_chapter = (
                        db.get(Chapter, preferences.default_chapter_id)
                        if preferences and preferences.default_chapter_id
                        else None
                    )
                    if (
                        default_chapter is not None
                        and default_chapter.subject_id == document.subject_id
                    ):
                        document.chapter_id = default_chapter.id
                        job.result = ImportResult(
                            subject_id=document.subject_id,
                            chapter_id=default_chapter.id,
                            chapter_name=default_chapter.name,
                            chapter_path=_chapter_path(
                                db, default_chapter
                            ).split(" > "),
                        ).model_dump()
                    else:
                        # Never guess another subject; archive at subject root.
                        document.chapter_id = None
                        document.subject_id = suggestion.subject_id
                        job.result = ImportResult(
                            subject_id=document.subject_id,
                            chapter_id=None,
                            chapter_name=None,
                            chapter_path=[],
                        ).model_dump()
                    _set_stage(db, job, "archiving", "保存资料归档", 60)
                    db.commit()
                else:
                    _set_stage(db, job, "archiving", "创建/匹配章节", 60)
                    subject = db.get(Subject, document.subject_id)
                    if subject is None:
                        _fail_import(db, job, "资料所属学科不存在")
                        return
                    job.result = archive_suggestion(
                        db,
                        document,
                        job,
                        subject,
                        suggestion,
                        create_missing=True,
                    ).model_dump()
                    db.commit()

            job = db.get(ImportJob, import_id)
            document = db.get(Document, job.document_id) if job else None
            if job is None or document is None:
                return
            if job.auto_analyze:
                started = _start_analysis(db, job, document, current_settings)
                if not started:
                    return
                analysis_id = job.analysis_job_id
            else:
                job.status = "completed"
                job.stage = "资料已归档"
                job.progress = 100
                job.finished_at = utc_now()
                db.commit()
                return

        except DomainError as exc:
            db.rollback()
            job = db.get(ImportJob, import_id)
            if job is not None:
                _fail_import(db, job, exc.message)
        except Exception:
            logger.exception("Import job %s failed", import_id)
            db.rollback()
            job = db.get(ImportJob, import_id)
            if job is not None:
                _fail_import(
                    db,
                    job,
                    "自动创建章节或归档失败，资料已保留，请重试",
                )

    if analysis_id:
        run_import_analysis(
            import_id,
            analysis_id,
            session_factory=session_factory,
            settings=current_settings,
            client=client,
        )


def run_import_analysis(
    import_id: str,
    analysis_job_id: str,
    *,
    session_factory: Callable[[], Session] = SessionLocal,
    settings: Settings | None = None,
    client: Any | None = None,
) -> None:
    current_settings = settings or get_settings()
    knowledge_service.run_extraction(
        analysis_job_id,
        session_factory=session_factory,
        client=client,
        settings=current_settings,
    )
    with session_factory() as db:
        job = db.get(ImportJob, import_id)
        if job is None:
            return
        analysis = db.get(KnowledgeExtractionJob, analysis_job_id)
        _finish_analysis(db, job, analysis)


def confirm_import(
    db: Session,
    import_id: str,
    payload: ImportConfirmRequest,
    *,
    settings: Settings | None = None,
) -> ImportRead:
    current_settings = settings or get_settings()
    job = get_import(db, import_id)
    if job.source_type == "external_json":
        from app.services.external_import import confirm_external_import

        return confirm_external_import(
            db,
            import_id,
            payload,
            settings=current_settings,
        )
    document = db.get(Document, job.document_id)
    if document is None:
        raise DomainError(404, "document_not_found", "导入资料不存在")
    if job.status not in {"awaiting_confirmation", "failed"}:
        raise DomainError(
            409,
            "import_not_confirmable",
            "当前导入任务不需要确认",
        )
    if document.status != "parsed":
        raise DomainError(
            409,
            "document_not_parsed",
            "资料尚未解析成功，不能确认归档；请先重试导入",
        )

    auto_analyze = (
        payload.auto_analyze
        if payload.auto_analyze is not None
        else job.auto_analyze
    )
    subject: Subject | None = None
    if payload.accept_suggestions and job.suggestion:
        suggestion = ImportSuggestion.model_validate(job.suggestion)
        subject = db.get(Subject, suggestion.subject_id)
        if subject is None:
            raise DomainError(404, "subject_not_found", "建议的学科已不存在")
        job.result = archive_suggestion(
            db,
            document,
            job,
            subject,
            suggestion,
            create_missing=payload.create_missing,
        ).model_dump()
    else:
        subject_id = payload.subject_id or document.subject_id
        subject = db.get(Subject, subject_id)
        if subject is None:
            raise DomainError(404, "subject_not_found", "学科不存在")
        chapter_id = payload.chapter_id
        chapter = db.get(Chapter, chapter_id) if chapter_id else None
        if chapter is not None and chapter.subject_id != subject.id:
            raise DomainError(
                422,
                "chapter_subject_mismatch",
                "所选章节不属于该学科",
            )
        document.subject_id = subject.id
        document.chapter_id = chapter.id if chapter else None
        db.execute(
            KnowledgePoint.__table__.update()
            .where(KnowledgePoint.document_id == document.id)
            .values(subject_id=subject.id, chapter_id=document.chapter_id)
        )
        job.result = ImportResult(
            subject_id=subject.id,
            chapter_id=document.chapter_id,
            chapter_name=chapter.name if chapter else None,
            chapter_path=[chapter.name] if chapter else [],
        ).model_dump()
        db.commit()

    job.error = None
    job.require_preview = False
    if auto_analyze:
        started = _start_analysis(db, job, document, current_settings)
        job = get_import(db, import_id)
        if started:
            # The API schedules run_import_analysis with the returned job id.
            return _import_read(db, job)
    job.status = "completed"
    job.stage = "资料已归档"
    job.progress = 100
    job.finished_at = utc_now()
    db.commit()
    db.refresh(job)
    return _import_read(db, job)


def retry_import(db: Session, import_id: str) -> ImportRead:
    job = get_import(db, import_id)
    if job.source_type == "external_json":
        from app.services.external_import import rebuild_external_preview

        return rebuild_external_preview(db, job)
    if job.status not in {"failed", "awaiting_confirmation"}:
        raise DomainError(409, "import_not_retryable", "只有失败或待确认的导入可以重试")
    job.status = "queued"
    job.stage = "等待重新处理"
    job.error = None
    job.progress = 0
    job.finished_at = None
    db.commit()
    db.refresh(job)
    return _import_read(db, job)
