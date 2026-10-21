from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.models import Chapter, Subject
from app.schemas.subject import SubjectCreate, SubjectRead, SubjectUpdate


def _chapter_count(db: Session, subject_id: str) -> int:
    return (
        db.scalar(
            select(func.count(Chapter.id)).where(
                Chapter.subject_id == subject_id
            )
        )
        or 0
    )


def _to_read(subject: Subject, chapter_count: int) -> SubjectRead:
    return SubjectRead(
        id=subject.id,
        name=subject.name,
        description=subject.description,
        color=subject.color,
        icon=subject.icon,
        sort_order=subject.sort_order,
        chapter_count=chapter_count,
        created_at=subject.created_at,
        updated_at=subject.updated_at,
    )


def _get_or_404(db: Session, subject_id: str) -> Subject:
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise DomainError(404, "subject_not_found", "学科不存在")
    return subject


def list_subjects(db: Session) -> list[SubjectRead]:
    chapter_count = (
        select(func.count(Chapter.id))
        .where(Chapter.subject_id == Subject.id)
        .correlate(Subject)
        .scalar_subquery()
    )
    rows = db.execute(
        select(Subject, chapter_count.label("chapter_count")).order_by(
            Subject.sort_order,
            Subject.created_at,
            Subject.name,
        )
    ).all()
    return [_to_read(subject, count) for subject, count in rows]


def get_subject(db: Session, subject_id: str) -> SubjectRead:
    subject = _get_or_404(db, subject_id)
    return _to_read(subject, _chapter_count(db, subject.id))


def create_subject(db: Session, payload: SubjectCreate) -> SubjectRead:
    sort_order = payload.sort_order
    if sort_order is None:
        current_max = db.scalar(select(func.max(Subject.sort_order)))
        sort_order = 0 if current_max is None else current_max + 10

    subject = Subject(
        name=payload.name,
        description=payload.description,
        color=payload.color,
        icon=payload.icon,
        sort_order=sort_order,
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return _to_read(subject, 0)


def update_subject(
    db: Session,
    subject_id: str,
    payload: SubjectUpdate,
) -> SubjectRead:
    subject = _get_or_404(db, subject_id)
    data = payload.model_dump(exclude_unset=True)

    if "name" in data and data["name"] is None:
        raise DomainError(422, "validation_error", "学科名称不能为空")
    if "sort_order" in data and data["sort_order"] is None:
        raise DomainError(422, "validation_error", "排序值不能为空")
    if "description" in data and data["description"] is None:
        data["description"] = ""

    for field, value in data.items():
        setattr(subject, field, value)

    db.commit()
    db.refresh(subject)
    return _to_read(subject, _chapter_count(db, subject.id))


def delete_subject(
    db: Session,
    subject_id: str,
    *,
    cascade: bool,
) -> None:
    subject = _get_or_404(db, subject_id)
    chapter_count = _chapter_count(db, subject.id)

    if chapter_count > 0 and not cascade:
        raise DomainError(
            409,
            "subject_has_chapters",
            f"该学科下仍有 {chapter_count} 个章节，请确认后再删除",
            chapter_count=chapter_count,
        )

    db.delete(subject)
    db.commit()
