from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.enums import (
    KnowledgeOrigin,
    JobStatus,
    ReviewStatus,
)
from app.core.authz import accessible_subject_ids, ensure_subject_access
from app.core.errors import DomainError
from app.db.base import utc_now
from app.models import (
    Document,
    DocumentChunk,
    KnowledgeExtractionJob,
    KnowledgePoint,
)
from app.schemas.knowledge import (
    DocumentBrief,
    DocumentKnowledgeResponse,
    KnowledgeBulkReviewRequest,
    KnowledgeListResponse,
    KnowledgeMergeRequest,
    KnowledgePointCreate,
    KnowledgePointDetail,
    KnowledgePointRead,
    KnowledgePointUpdate,
    KnowledgeReviewStats,
)
from app.services.knowledge_common import (
    build_point_tree,
    descendant_ids,
    get_point_or_404,
    normalize_name,
    point_detail,
    point_stats,
    unique_strings,
    validate_point_parent,
)
from app.services.mappers import job_read, point_read


def _get_document_or_404(
    db: Session, document_id: str, *, write: bool = False
) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise DomainError(404, "document_not_found", "资料不存在")
    ensure_subject_access(db, document.subject_id, write=write)
    return document


def _document_points(db: Session, document_id: str) -> list[KnowledgePoint]:
    return db.scalars(
        select(KnowledgePoint)
        .where(KnowledgePoint.document_id == document_id)
        .order_by(KnowledgePoint.created_at, KnowledgePoint.name)
    ).all()


def _failed_jobs(db: Session, document_id: str) -> int:
    return db.scalar(
        select(func.count(KnowledgeExtractionJob.id)).where(
            KnowledgeExtractionJob.document_id == document_id,
            KnowledgeExtractionJob.status == JobStatus.FAILED.value,
        )
    ) or 0


def get_document_knowledge(
    db: Session,
    document_id: str,
) -> DocumentKnowledgeResponse:
    document = _get_document_or_404(db, document_id)
    points = _document_points(db, document_id)
    chunk_count = db.scalar(
        select(func.count(DocumentChunk.id)).where(
            DocumentChunk.document_id == document_id
        )
    ) or 0
    latest_job = db.scalar(
        select(KnowledgeExtractionJob)
        .where(KnowledgeExtractionJob.document_id == document_id)
        .order_by(KnowledgeExtractionJob.created_at.desc())
        .limit(1)
    )
    return DocumentKnowledgeResponse(
        document=DocumentBrief(
            id=document.id,
            name=document.name,
            status=document.status,
            chunk_count=chunk_count,
        ),
        stats=point_stats(points, failed_jobs=_failed_jobs(db, document_id)),
        points=build_point_tree(points),
        latest_job=job_read(latest_job),
    )


def list_knowledge_points(
    db: Session,
    *,
    document_id: str | None = None,
    subject_id: str | None = None,
    chapter_id: str | None = None,
    review_status: str | None = None,
    point_type: str | None = None,
    origin: str | None = None,
    q: str | None = None,
    needs_review: bool | None = None,
    limit: int = 500,
    offset: int = 0,
) -> KnowledgeListResponse:
    conditions = []
    allowed = accessible_subject_ids(db)
    if allowed is not None:
        conditions.append(KnowledgePoint.subject_id.in_(allowed) if allowed else False)
    if document_id:
        conditions.append(KnowledgePoint.document_id == document_id)
    if subject_id:
        conditions.append(KnowledgePoint.subject_id == subject_id)
    if chapter_id:
        conditions.append(KnowledgePoint.chapter_id == chapter_id)
    if review_status:
        conditions.append(KnowledgePoint.review_status == review_status)
    if point_type:
        conditions.append(KnowledgePoint.point_type == point_type)
    if origin:
        conditions.append(KnowledgePoint.origin == origin)
    if needs_review is not None:
        conditions.append(KnowledgePoint.needs_review.is_(needs_review))
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        conditions.append(
            or_(
                KnowledgePoint.name.ilike(pattern),
                KnowledgePoint.explanation.ilike(pattern),
            )
        )

    statement = select(KnowledgePoint)
    if conditions:
        statement = statement.where(*conditions)
    total = db.scalar(
        select(func.count(KnowledgePoint.id)).where(*conditions)
    ) or 0
    points = db.scalars(
        statement.order_by(
            KnowledgePoint.created_at,
            KnowledgePoint.name,
        )
        .offset(max(0, offset))
        .limit(max(1, min(limit, 2000)))
    ).all()
    return KnowledgeListResponse(
        points=[point_read(point) for point in points],
        stats=point_stats(points),
        total=total,
    )


def get_point_detail(db: Session, point_id: str) -> KnowledgePointDetail:
    point = get_point_or_404(db, point_id)
    return point_detail(db, point)


def create_manual_point(
    db: Session,
    payload: KnowledgePointCreate,
) -> KnowledgePointDetail:
    document = _get_document_or_404(db, payload.document_id, write=True)
    validate_point_parent(
        db,
        document_id=document.id,
        subject_id=document.subject_id,
        chapter_id=document.chapter_id,
        parent_id=payload.parent_id,
    )
    point = KnowledgePoint(
        subject_id=document.subject_id,
        chapter_id=document.chapter_id,
        document_id=document.id,
        parent_id=payload.parent_id,
        name=payload.name,
        point_type=payload.type.value,
        explanation=payload.explanation,
        core_points=unique_strings(payload.core_points),
        conditions=payload.conditions,
        review_note=payload.review_note,
        source_locator="人工新增",
        needs_review=False,
        origin=KnowledgeOrigin.MANUAL.value,
        review_status=ReviewStatus.PENDING.value,
    )
    db.add(point)
    db.commit()
    db.refresh(point)
    return point_detail(db, point)


def update_point(
    db: Session,
    point_id: str,
    payload: KnowledgePointUpdate,
) -> KnowledgePointDetail:
    point = get_point_or_404(db, point_id, write=True)
    data = payload.model_dump(exclude_unset=True)

    if "name" in data and data["name"] is None:
        raise DomainError(422, "validation_error", "知识点名称不能为空")
    if "explanation" in data and data["explanation"] is None:
        raise DomainError(422, "validation_error", "知识点解释不能为空")
    if "type" in data and data["type"] is None:
        raise DomainError(422, "validation_error", "知识点类型不能为空")

    if "parent_id" in data:
        validate_point_parent(
            db,
            document_id=point.document_id,
            subject_id=point.subject_id,
            chapter_id=point.chapter_id,
            parent_id=data["parent_id"],
            point_id=point.id,
        )

    content_changed = False
    content_fields = {
        "name": lambda value: point.name != value,
        "type": lambda value: point.point_type != value.value,
        "explanation": lambda value: point.explanation != value,
        "core_points": lambda value: list(point.core_points or []) != list(value),
        "conditions": lambda value: point.conditions != value,
    }
    for field, differs in content_fields.items():
        if field in data and data[field] is not None and differs(data[field]):
            content_changed = True

    for field, value in data.items():
        if field == "type" and value is not None:
            point.point_type = value.value
        elif field == "core_points" and value is not None:
            point.core_points = unique_strings(value)
        else:
            setattr(point, field, value)

    if content_changed:
        point.review_status = ReviewStatus.PENDING.value
        point.reviewed_at = None
        point.published_at = None
        point.needs_review = True
    db.commit()
    db.refresh(point)
    return point_detail(db, point)


def _apply_review_status(point: KnowledgePoint, status: ReviewStatus) -> None:
    point.review_status = status.value
    point.reviewed_at = utc_now()
    if status == ReviewStatus.APPROVED:
        point.published_at = utc_now()
        point.needs_review = False
    else:
        point.published_at = None
        if status == ReviewStatus.NEEDS_REVISION:
            point.needs_review = True


def review_point(
    db: Session,
    point_id: str,
    status: ReviewStatus,
) -> KnowledgePointDetail:
    point = get_point_or_404(db, point_id)
    _apply_review_status(point, status)
    db.commit()
    db.refresh(point)
    return point_detail(db, point)


def bulk_review(
    db: Session,
    payload: KnowledgeBulkReviewRequest,
) -> int:
    ids = list(dict.fromkeys(payload.ids))
    points = db.scalars(
        select(KnowledgePoint).where(KnowledgePoint.id.in_(ids))
    ).all()
    if len(points) != len(ids):
        raise DomainError(
            404,
            "knowledge_point_not_found",
            "部分知识点不存在，请刷新后重试",
        )
    for point in points:
        ensure_subject_access(db, point.subject_id, write=True)
        _apply_review_status(point, payload.status)
    db.commit()
    return len(points)


def delete_point(db: Session, point_id: str, *, cascade: bool) -> None:
    point = get_point_or_404(db, point_id, write=True)
    descendants = descendant_ids(db, point)
    if descendants and not cascade:
        raise DomainError(
            409,
            "knowledge_point_has_children",
            f"该知识点下仍有 {len(descendants)} 个后代知识点，请确认后再删除",
            descendant_count=len(descendants),
        )
    db.delete(point)
    db.commit()


def merge_points(
    db: Session,
    payload: KnowledgeMergeRequest,
) -> KnowledgePointDetail:
    source_ids = list(dict.fromkeys(payload.source_ids))
    points = db.scalars(
        select(KnowledgePoint).where(KnowledgePoint.id.in_(source_ids))
    ).all()
    if len(points) != len(source_ids):
        raise DomainError(
            404,
            "knowledge_point_not_found",
            "部分待合并知识点不存在，请刷新后重试",
        )
    for point in points:
        ensure_subject_access(db, point.subject_id, write=True)
    document_ids = {point.document_id for point in points}
    if len(document_ids) != 1:
        raise DomainError(
            422,
            "merge_scope_mismatch",
            "只能合并同一资料中的知识点",
        )
    by_id = {point.id: point for point in points}
    target = by_id[source_ids[0]]
    others = [by_id[source_id] for source_id in source_ids[1:]]
    other_ids = {point.id for point in others}

    if target.parent_id in other_ids:
        target.parent_id = None
    for point in others:
        for child in list(point.children):
            if child.id not in source_ids:
                child.parent_id = target.id

    target.name = payload.name or target.name
    target.explanation = payload.explanation or "；".join(
        unique_strings([target.explanation, *(point.explanation for point in others)])
    )
    target.core_points = unique_strings(
        [
            *(target.core_points or []),
            *[item for point in others for item in (point.core_points or [])],
        ]
    )
    target.conditions = "；".join(
        unique_strings(
            [
                item
                for value in [
                    target.conditions,
                    *(point.conditions for point in others),
                ]
                if value
                for item in [value]
            ]
        )
    ) or None
    target.source_quote = "\n\n".join(
        unique_strings(
            [
                item
                for value in [
                    target.source_quote,
                    *(point.source_quote for point in others),
                ]
                if value
                for item in [value]
            ]
        )
    )[:4000] or None
    target.source_locator = "；".join(
        unique_strings(
            [
                item
                for value in [
                    target.source_locator,
                    *(point.source_locator for point in others),
                ]
                if value
                for item in [value]
            ]
        )
    )[:200] or None
    target.needs_review = True
    target.review_status = ReviewStatus.PENDING.value
    target.published_at = None

    for point in others:
        db.delete(point)
    db.commit()
    db.refresh(target)
    return point_detail(db, target)
