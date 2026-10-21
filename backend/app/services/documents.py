from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.enums import DocumentStatus, JobStatus
from app.core.errors import DomainError
from app.db.base import utc_now
from app.db.session import SessionLocal
from app.models import (
    Chapter,
    Document,
    DocumentChunk,
    KnowledgeExtractionJob,
    KnowledgePoint,
    Subject,
)
from app.schemas.document import DocumentDetail, DocumentRead, DocumentUpdate
from app.services.chunking import build_chunks
from app.services.mappers import chunk_read, job_read
from app.services.parsing import (
    detect_and_validate_file,
    normalize_extension,
    parse_document,
)

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name.strip().strip(".")
    cleaned = "".join(
        character
        for character in name
        if character >= " " and character not in '<>:"/\\|?*'
    )
    cleaned = cleaned[:180].strip().strip(".")
    return cleaned or "document"


def _upload_root(settings: Settings) -> Path:
    root = settings.resolved(Path(settings.upload_dir))
    root.mkdir(parents=True, exist_ok=True)
    return root


def document_path(document: Document, settings: Settings) -> Path:
    root = _upload_root(settings)
    path = (root / document.storage_name).resolve()
    if root != path.parent and root not in path.parents:
        raise DomainError(500, "unsafe_storage_path", "资料存储路径不安全")
    return path


def _get_subject_or_404(db: Session, subject_id: str) -> Subject:
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise DomainError(404, "subject_not_found", "学科不存在")
    return subject


def _validate_chapter(
    db: Session,
    subject_id: str,
    chapter_id: str | None,
) -> Chapter | None:
    if chapter_id is None:
        return None
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        raise DomainError(422, "chapter_not_found", "所属章节不存在")
    if chapter.subject_id != subject_id:
        raise DomainError(
            422,
            "chapter_subject_mismatch",
            "所选章节不属于该学科",
        )
    return chapter


async def create_document_from_upload(
    db: Session,
    upload: UploadFile,
    *,
    subject_id: str,
    chapter_id: str | None,
    name: str | None,
    force: bool,
    settings: Settings | None = None,
    dedupe_global: bool = False,
    dedupe_subject: bool = False,
    return_existing: bool = False,
) -> DocumentRead:
    current_settings = settings or get_settings()
    _get_subject_or_404(db, subject_id)
    _validate_chapter(db, subject_id, chapter_id)

    original_name = sanitize_filename(upload.filename or "")
    extension = normalize_extension(original_name)
    root = _upload_root(current_settings)
    document_id = str(uuid4())
    storage_name = f"{document_id}{extension}"
    target_path = (root / storage_name).resolve()
    if root != target_path.parent and root not in target_path.parents:
        raise DomainError(500, "unsafe_storage_path", "资料存储路径不安全")

    digest = hashlib.sha256()
    size = 0
    committed = False

    try:
        with target_path.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > current_settings.max_upload_bytes:
                    raise DomainError(
                        413,
                        "file_too_large",
                        f"文件超过 {current_settings.max_upload_bytes // (1024 * 1024)} MB 限制",
                    )
                digest.update(chunk)
                output.write(chunk)

        if size == 0:
            raise DomainError(422, "empty_file", "文件内容为空")

        mime_type = detect_and_validate_file(target_path, extension)

        digest_value = digest.hexdigest()
        if dedupe_global:
            duplicate_statement = select(Document).where(
                Document.sha256 == digest_value,
            )
        elif dedupe_subject:
            duplicate_statement = select(Document).where(
                Document.sha256 == digest_value,
                Document.subject_id == subject_id,
            )
        else:
            duplicate_statement = select(Document).where(
                Document.sha256 == digest_value,
                Document.subject_id == subject_id,
            )
            if chapter_id is None:
                duplicate_statement = duplicate_statement.where(
                    Document.chapter_id.is_(None)
                )
            else:
                duplicate_statement = duplicate_statement.where(
                    Document.chapter_id == chapter_id
                )
        duplicate = db.scalar(duplicate_statement)
        if duplicate is not None and not force:
            if return_existing:
                target_path.unlink(missing_ok=True)
                db.rollback()
                return _document_read(db, duplicate, duplicate=True)
            raise DomainError(
                409,
                "duplicate_document",
                "同一章节下已上传过相同内容的资料",
                existing_document_id=duplicate.id,
                existing_document_name=duplicate.name,
            )

        display_name = (name or Path(original_name).stem).strip()
        if not display_name:
            display_name = Path(original_name).stem or "未命名资料"
        if len(display_name) > 240:
            raise DomainError(422, "validation_error", "资料名称不能超过 240 个字符")

        document = Document(
            id=document_id,
            subject_id=subject_id,
            chapter_id=chapter_id,
            name=display_name,
            original_filename=original_name,
            storage_name=storage_name,
            mime_type=mime_type,
            extension=extension,
            size_bytes=size,
            sha256=digest_value,
            status=DocumentStatus.UPLOADED.value,
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        committed = True
        return _document_read(db, document)
    except Exception:
        if not committed:
            target_path.unlink(missing_ok=True)
        db.rollback()
        raise


def _counts(db: Session, document_id: str) -> tuple[int, int, int]:
    chunk_count = db.scalar(
        select(func.count(DocumentChunk.id)).where(
            DocumentChunk.document_id == document_id
        )
    ) or 0
    point_count = db.scalar(
        select(func.count(KnowledgePoint.id)).where(
            KnowledgePoint.document_id == document_id
        )
    ) or 0
    approved_count = db.scalar(
        select(func.count(KnowledgePoint.id)).where(
            KnowledgePoint.document_id == document_id,
            KnowledgePoint.review_status == "approved",
        )
    ) or 0
    return chunk_count, point_count, approved_count


def _running_job_count(db: Session, document_id: str) -> int:
    return db.scalar(
        select(func.count(KnowledgeExtractionJob.id)).where(
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
    ) or 0


def _document_read(
    db: Session,
    document: Document,
    *,
    duplicate: bool = False,
) -> DocumentRead:
    chunk_count, point_count, approved_count = _counts(db, document.id)
    return DocumentRead(
        id=document.id,
        subject_id=document.subject_id,
        chapter_id=document.chapter_id,
        chapter_name=document.chapter.name if document.chapter else None,
        name=document.name,
        content_title=document.content_title,
        original_filename=document.original_filename,
        mime_type=document.mime_type,
        extension=document.extension,
        size_bytes=document.size_bytes,
        sha256=document.sha256,
        status=document.status,
        parse_error=document.parse_error,
        parse_warnings=document.parse_warnings,
        page_count=document.page_count,
        slide_count=document.slide_count,
        chunk_count=chunk_count,
        knowledge_point_count=point_count,
        approved_count=approved_count,
        duplicate=duplicate,
        uploaded_at=document.uploaded_at,
        parsed_at=document.parsed_at,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def list_documents(
    db: Session,
    *,
    subject_id: str | None = None,
    chapter_id: str | None = None,
    status: str | None = None,
) -> list[DocumentRead]:
    statement = select(Document).order_by(Document.uploaded_at.desc())
    if subject_id:
        statement = statement.where(Document.subject_id == subject_id)
    if chapter_id:
        statement = statement.where(Document.chapter_id == chapter_id)
    if status:
        statement = statement.where(Document.status == status)
    return [_document_read(db, document) for document in db.scalars(statement).all()]


def get_document(db: Session, document_id: str) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise DomainError(404, "document_not_found", "资料不存在")
    return document


def update_document(
    db: Session,
    document_id: str,
    payload: DocumentUpdate,
) -> DocumentRead:
    document = get_document(db, document_id)
    changed_fields = payload.model_fields_set
    subject_id = payload.subject_id or document.subject_id
    _get_subject_or_404(db, subject_id)

    subject_changed = subject_id != document.subject_id
    if "chapter_id" in changed_fields:
        chapter_id = payload.chapter_id
    elif subject_changed:
        chapter_id = None
    else:
        chapter_id = document.chapter_id
    _validate_chapter(db, subject_id, chapter_id)

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise DomainError(422, "validation_error", "资料名称不能为空")
        if len(name) > 240:
            raise DomainError(422, "validation_error", "资料名称不能超过 240 个字符")
        document.name = name

    if subject_changed or chapter_id != document.chapter_id:
        document.subject_id = subject_id
        document.chapter_id = chapter_id
        # Keep existing knowledge points attached to the same folder.
        db.execute(
            update(KnowledgePoint)
            .where(KnowledgePoint.document_id == document.id)
            .values(subject_id=subject_id, chapter_id=chapter_id)
        )

    db.commit()
    db.refresh(document)
    return _document_read(db, document)


def get_document_detail(
    db: Session,
    document_id: str,
) -> DocumentDetail:
    document = get_document(db, document_id)
    chunks = db.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    ).all()
    latest_job = db.scalar(
        select(KnowledgeExtractionJob)
        .where(KnowledgeExtractionJob.document_id == document_id)
        .order_by(KnowledgeExtractionJob.created_at.desc())
        .limit(1)
    )
    read = _document_read(db, document)
    return DocumentDetail(
        **read.model_dump(),
        chunks=[chunk_read(chunk) for chunk in chunks],
        latest_job=job_read(latest_job),
    )


def process_document(
    document_id: str,
    *,
    session_factory: Callable[[], Session] = SessionLocal,
    settings: Settings | None = None,
) -> None:
    current_settings = settings or get_settings()
    with session_factory() as db:
        document = db.get(Document, document_id)
        if document is None:
            return
        document.status = DocumentStatus.PARSING.value
        document.parse_error = None
        document.parse_warnings = None
        db.commit()

        try:
            path = document_path(document, current_settings)
            if not path.exists():
                raise DomainError(422, "file_missing", "资料文件已不存在，请重新上传")
            parsed = parse_document(path, document.extension, document.original_filename)
            document.content_title = parsed.title
            document.page_count = parsed.page_count
            document.slide_count = parsed.slide_count
            document.parse_warnings = "\n".join(parsed.warnings) or None
            document.parsed_at = utc_now()

            if parsed.needs_ocr:
                document.status = DocumentStatus.NEEDS_OCR.value
                document.parse_error = (
                    "未能从 PDF 中提取到可读文字，文件可能是扫描版；"
                    "当前未启用 OCR，暂时无法可靠提取内容。"
                )
                db.commit()
                return

            drafts = build_chunks(
                parsed,
                max_chars=current_settings.chunk_max_chars,
                min_chars=current_settings.chunk_min_chars,
            )
            if not drafts:
                raise DomainError(422, "no_extractable_text", "没有可保存的正文分块")

            db.execute(
                delete(DocumentChunk).where(
                    DocumentChunk.document_id == document.id
                )
            )
            for index, draft in enumerate(drafts):
                db.add(
                    DocumentChunk(
                        document_id=document.id,
                        chunk_index=index,
                        heading_path=draft.heading_path,
                        heading_level=draft.heading_level,
                        content=draft.content,
                        page_start=draft.page_start,
                        page_end=draft.page_end,
                        slide_number=draft.slide_number,
                        char_start=draft.char_start,
                        char_end=draft.char_end,
                        block_start=draft.block_start,
                        block_end=draft.block_end,
                        location_label=draft.location_label,
                    )
                )
            document.status = DocumentStatus.PARSED.value
            document.parse_error = None
            db.commit()
        except Exception as exc:
            logger.exception("Failed to parse document %s", document_id)
            db.rollback()
            document = db.get(Document, document_id)
            if document is not None:
                document.status = DocumentStatus.FAILED.value
                document.parse_error = _safe_parse_error(exc)
                document.parsed_at = utc_now()
                db.commit()


def _safe_parse_error(exc: Exception) -> str:
    if isinstance(exc, DomainError):
        return exc.message
    return "解析失败，请检查文件是否损坏或格式是否受支持"


def reset_document_for_parse(db: Session, document_id: str) -> DocumentRead:
    document = get_document(db, document_id)
    if document.status == DocumentStatus.PARSING.value:
        raise DomainError(409, "document_parsing", "资料正在解析中，请稍后")
    if _running_job_count(db, document_id):
        raise DomainError(
            409,
            "document_job_running",
            "资料仍有 AI 任务在运行，请等待完成后再重试解析",
        )
    if document.status == DocumentStatus.PARSED.value:
        raise DomainError(
            409,
            "document_already_parsed",
            "资料已解析；如需重新解析，请先删除关联知识点或上传新资料",
        )
    _, point_count, _ = _counts(db, document_id)
    if point_count:
        raise DomainError(
            409,
            "document_has_knowledge_points",
            f"资料关联 {point_count} 个知识点，重新解析会使来源失效；"
            "请先处理这些知识点",
            knowledge_point_count=point_count,
        )
    document.status = DocumentStatus.UPLOADED.value
    document.parse_error = None
    document.parse_warnings = None
    db.commit()
    db.refresh(document)
    return _document_read(db, document)


def delete_document(
    db: Session,
    document_id: str,
    *,
    cascade: bool,
    settings: Settings | None = None,
) -> None:
    current_settings = settings or get_settings()
    document = get_document(db, document_id)
    _, point_count, approved_count = _counts(db, document.id)
    running_job = _running_job_count(db, document_id)
    if running_job:
        raise DomainError(
            409,
            "document_job_running",
            "资料仍有 AI 任务在运行，请等待完成后再删除",
        )
    if point_count and not cascade:
        raise DomainError(
            409,
            "document_has_knowledge_points",
            f"资料关联 {point_count} 个知识点（其中 {approved_count} 个已通过），"
            "请确认后再删除",
            knowledge_point_count=point_count,
            approved_count=approved_count,
        )

    path = document_path(document, current_settings)
    # Chapters created by this document keep their provenance but must not
    # point at a deleted document id.
    db.execute(
        update(Chapter)
        .where(Chapter.source_document_id == document_id)
        .values(source_document_id=None)
    )
    db.delete(document)
    db.commit()
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not remove stored file for document %s", document_id)
