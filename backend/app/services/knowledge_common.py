from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import ReviewStatus
from app.core.authz import ensure_subject_access
from app.core.errors import DomainError
from app.models import (
    Chapter,
    Document,
    KnowledgePoint,
    Subject,
)
from app.schemas.knowledge import (
    KnowledgePointDetail,
    KnowledgePointTreeNode,
    KnowledgeReviewStats,
)
from app.services.mappers import point_read


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_name(value: str) -> str:
    return re.sub(r"[\s\W_]+", "", value.lower())


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned:
            continue
        key = normalize_text(cleaned)
        if key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def point_stats(
    points: list[KnowledgePoint],
    *,
    failed_jobs: int = 0,
) -> KnowledgeReviewStats:
    statuses = {
        ReviewStatus.PENDING.value: 0,
        ReviewStatus.APPROVED.value: 0,
        ReviewStatus.NEEDS_REVISION.value: 0,
        ReviewStatus.IGNORED.value: 0,
    }
    for point in points:
        if point.review_status in statuses:
            statuses[point.review_status] += 1
    return KnowledgeReviewStats(
        total=len(points),
        pending=statuses[ReviewStatus.PENDING.value],
        approved=statuses[ReviewStatus.APPROVED.value],
        needs_revision=statuses[ReviewStatus.NEEDS_REVISION.value],
        ignored=statuses[ReviewStatus.IGNORED.value],
        needs_review=sum(1 for point in points if point.needs_review),
        duplicates=sum(1 for point in points if point.duplicate_of_id),
        failed_jobs=failed_jobs,
    )


def build_point_tree(
    points: list[KnowledgePoint],
) -> list[KnowledgePointTreeNode]:
    nodes = {
        point.id: KnowledgePointTreeNode(
            **point_read(point).model_dump(),
            children=[],
        )
        for point in points
    }
    roots: list[KnowledgePointTreeNode] = []
    for point in points:
        node = nodes[point.id]
        if point.parent_id and point.parent_id in nodes:
            nodes[point.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


def point_detail(db: Session, point: KnowledgePoint) -> KnowledgePointDetail:
    document = db.get(Document, point.document_id)
    subject = db.get(Subject, point.subject_id)
    chapter = db.get(Chapter, point.chapter_id) if point.chapter_id else None
    chunk = point.source_chunk
    read = point_read(point)
    return KnowledgePointDetail(
        **read.model_dump(),
        document_name=document.name if document else "未知资料",
        subject_name=subject.name if subject else "未知学科",
        chapter_name=chapter.name if chapter else None,
        source_chunk_content=chunk.content if chunk else None,
        source_chunk_heading=chunk.heading_path if chunk else None,
    )


def get_point_or_404(
    db: Session, point_id: str, *, write: bool = False
) -> KnowledgePoint:
    point = db.get(KnowledgePoint, point_id)
    if point is None:
        raise DomainError(404, "knowledge_point_not_found", "知识点不存在")
    ensure_subject_access(db, point.subject_id, write=write)
    return point


def validate_point_parent(
    db: Session,
    *,
    document_id: str,
    subject_id: str,
    chapter_id: str | None,
    parent_id: str | None,
    point_id: str | None = None,
) -> KnowledgePoint | None:
    if parent_id is None:
        return None
    parent = db.get(KnowledgePoint, parent_id)
    if parent is None:
        raise DomainError(422, "parent_not_found", "父知识点不存在")
    if (
        parent.document_id != document_id
        or parent.subject_id != subject_id
        or parent.chapter_id != chapter_id
    ):
        raise DomainError(
            422,
            "parent_scope_mismatch",
            "父知识点必须属于同一资料、学科和章节",
        )
    if point_id is not None:
        seen: set[str] = set()
        current: KnowledgePoint | None = parent
        while current is not None:
            if current.id == point_id:
                raise DomainError(
                    422,
                    "knowledge_point_cycle",
                    "知识点不能成为自己的祖先",
                )
            if current.id in seen:
                raise DomainError(
                    409,
                    "knowledge_tree_invalid",
                    "知识点层级存在异常循环",
                )
            seen.add(current.id)
            current = (
                db.get(KnowledgePoint, current.parent_id)
                if current.parent_id
                else None
            )
    return parent


def descendant_ids(db: Session, point: KnowledgePoint) -> set[str]:
    points = db.scalars(
        select(KnowledgePoint).where(
            KnowledgePoint.document_id == point.document_id
        )
    ).all()
    children: dict[str | None, list[str]] = {}
    for item in points:
        children.setdefault(item.parent_id, []).append(item.id)
    result: set[str] = set()
    stack = list(children.get(point.id, []))
    while stack:
        current_id = stack.pop()
        if current_id in result:
            continue
        result.add(current_id)
        stack.extend(children.get(current_id, []))
    return result
