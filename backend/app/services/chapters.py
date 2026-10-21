from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.models import Chapter, Subject
from app.schemas.chapter import (
    ChapterCreate,
    ChapterDetail,
    ChapterParentSummary,
    ChapterPathItem,
    ChapterRead,
    ChapterTreeNode,
    ChapterUpdate,
)
from app.schemas.subject import SubjectSummary


def _get_subject_or_404(db: Session, subject_id: str) -> Subject:
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise DomainError(404, "subject_not_found", "学科不存在")
    return subject


def _get_chapter_or_404(db: Session, chapter_id: str) -> Chapter:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        raise DomainError(404, "chapter_not_found", "章节不存在")
    return chapter


def _sibling_conditions(
    subject_id: str,
    parent_id: str | None,
) -> list[object]:
    conditions: list[object] = [Chapter.subject_id == subject_id]
    if parent_id is None:
        conditions.append(Chapter.parent_id.is_(None))
    else:
        conditions.append(Chapter.parent_id == parent_id)
    return conditions


def _next_sort_order(
    db: Session,
    subject_id: str,
    parent_id: str | None,
    *,
    exclude_id: str | None = None,
) -> int:
    statement = select(func.max(Chapter.sort_order)).where(
        *_sibling_conditions(subject_id, parent_id)
    )
    if exclude_id is not None:
        statement = statement.where(Chapter.id != exclude_id)
    current_max = db.scalar(statement)
    return 0 if current_max is None else current_max + 10


def _validate_parent(
    db: Session,
    subject_id: str,
    parent_id: str | None,
    *,
    chapter_id: str | None = None,
) -> Chapter | None:
    if parent_id is None:
        return None

    parent = db.get(Chapter, parent_id)
    if parent is None:
        raise DomainError(422, "parent_not_found", "父章节不存在")
    if parent.subject_id != subject_id:
        raise DomainError(
            422,
            "parent_subject_mismatch",
            "父章节不属于当前学科",
        )

    if chapter_id is not None:
        seen: set[str] = set()
        current: Chapter | None = parent
        while current is not None:
            if current.id == chapter_id:
                raise DomainError(
                    422,
                    "chapter_cycle",
                    "章节不能成为自己的祖先",
                )
            if current.id in seen:
                raise DomainError(
                    409,
                    "chapter_tree_invalid",
                    "章节层级存在异常循环",
                )
            seen.add(current.id)
            current = (
                db.get(Chapter, current.parent_id)
                if current.parent_id
                else None
            )

    return parent


def _descendant_ids(
    db: Session,
    subject_id: str,
    chapter_id: str,
) -> set[str]:
    chapters = db.scalars(
        select(Chapter).where(Chapter.subject_id == subject_id)
    ).all()
    children_by_parent: dict[str | None, list[str]] = defaultdict(list)
    for chapter in chapters:
        children_by_parent[chapter.parent_id].append(chapter.id)

    result: set[str] = set()
    stack = list(children_by_parent.get(chapter_id, []))
    while stack:
        current_id = stack.pop()
        if current_id in result:
            continue
        result.add(current_id)
        stack.extend(children_by_parent.get(current_id, []))
    return result


def _to_read(chapter: Chapter) -> ChapterRead:
    return ChapterRead(
        id=chapter.id,
        subject_id=chapter.subject_id,
        parent_id=chapter.parent_id,
        name=chapter.name,
        description=chapter.description,
        sort_order=chapter.sort_order,
        source_document_id=chapter.source_document_id,
        source_import_job_id=chapter.source_import_job_id,
        source_slide=chapter.source_slide,
        created_at=chapter.created_at,
        updated_at=chapter.updated_at,
    )


def _to_node(chapter: Chapter) -> ChapterTreeNode:
    return ChapterTreeNode(
        id=chapter.id,
        subject_id=chapter.subject_id,
        parent_id=chapter.parent_id,
        name=chapter.name,
        description=chapter.description,
        sort_order=chapter.sort_order,
        source_document_id=chapter.source_document_id,
        source_import_job_id=chapter.source_import_job_id,
        source_slide=chapter.source_slide,
        created_at=chapter.created_at,
        updated_at=chapter.updated_at,
        children=[],
    )


def list_chapter_tree(
    db: Session,
    subject_id: str,
) -> list[ChapterTreeNode]:
    _get_subject_or_404(db, subject_id)
    chapters = db.scalars(
        select(Chapter)
        .where(Chapter.subject_id == subject_id)
        .order_by(Chapter.sort_order, Chapter.created_at, Chapter.name)
    ).all()

    nodes = {chapter.id: _to_node(chapter) for chapter in chapters}
    roots: list[ChapterTreeNode] = []

    for chapter in chapters:
        node = nodes[chapter.id]
        if chapter.parent_id is None:
            roots.append(node)
        elif chapter.parent_id in nodes:
            nodes[chapter.parent_id].children.append(node)
        else:
            raise DomainError(
                409,
                "chapter_tree_invalid",
                "章节存在无效的父级关联",
            )

    reachable: set[str] = set()

    def walk(node: ChapterTreeNode) -> None:
        if node.id in reachable:
            raise DomainError(
                409,
                "chapter_tree_invalid",
                "章节层级存在异常循环",
            )
        reachable.add(node.id)
        for child in node.children:
            walk(child)

    for root in roots:
        walk(root)

    if len(reachable) != len(chapters):
        raise DomainError(
            409,
            "chapter_tree_invalid",
            "章节层级存在异常循环或孤立节点",
        )

    return roots


def get_chapter_detail(db: Session, chapter_id: str) -> ChapterDetail:
    chapter = _get_chapter_or_404(db, chapter_id)
    subject = db.get(Subject, chapter.subject_id)
    if subject is None:
        raise DomainError(409, "chapter_tree_invalid", "章节所属学科不存在")

    parent = db.get(Chapter, chapter.parent_id) if chapter.parent_id else None
    path_nodes: list[Chapter] = []
    seen: set[str] = set()
    current = parent
    while current is not None:
        if current.id in seen:
            raise DomainError(
                409,
                "chapter_tree_invalid",
                "章节层级存在异常循环",
            )
        seen.add(current.id)
        path_nodes.append(current)
        current = (
            db.get(Chapter, current.parent_id)
            if current.parent_id
            else None
        )

    path = [
        ChapterPathItem(id=node.id, name=node.name)
        for node in reversed(path_nodes)
    ]
    descendants = _descendant_ids(db, chapter.subject_id, chapter.id)

    return ChapterDetail(
        id=chapter.id,
        subject_id=chapter.subject_id,
        parent_id=chapter.parent_id,
        name=chapter.name,
        description=chapter.description,
        sort_order=chapter.sort_order,
        source_document_id=chapter.source_document_id,
        source_import_job_id=chapter.source_import_job_id,
        source_slide=chapter.source_slide,
        created_at=chapter.created_at,
        updated_at=chapter.updated_at,
        subject=SubjectSummary.model_validate(subject),
        parent=(
            ChapterParentSummary(id=parent.id, name=parent.name)
            if parent is not None
            else None
        ),
        path=path,
        descendant_count=len(descendants),
    )


def create_chapter(
    db: Session,
    subject_id: str,
    payload: ChapterCreate,
) -> ChapterRead:
    _get_subject_or_404(db, subject_id)
    _validate_parent(db, subject_id, payload.parent_id)

    sort_order = payload.sort_order
    if sort_order is None:
        sort_order = _next_sort_order(db, subject_id, payload.parent_id)

    chapter = Chapter(
        subject_id=subject_id,
        parent_id=payload.parent_id,
        name=payload.name,
        description=payload.description,
        sort_order=sort_order,
    )
    db.add(chapter)
    db.commit()
    db.refresh(chapter)
    return _to_read(chapter)


def update_chapter(
    db: Session,
    chapter_id: str,
    payload: ChapterUpdate,
) -> ChapterRead:
    chapter = _get_chapter_or_404(db, chapter_id)
    data = payload.model_dump(exclude_unset=True)

    if "name" in data and data["name"] is None:
        raise DomainError(422, "validation_error", "章节名称不能为空")
    if "sort_order" in data and data["sort_order"] is None:
        raise DomainError(422, "validation_error", "排序值不能为空")
    if "description" in data and data["description"] is None:
        data["description"] = ""

    parent_changed = False
    new_parent_id = chapter.parent_id
    if "parent_id" in data:
        new_parent_id = data["parent_id"]
        _validate_parent(
            db,
            chapter.subject_id,
            new_parent_id,
            chapter_id=chapter.id,
        )
        parent_changed = new_parent_id != chapter.parent_id

    if parent_changed and "sort_order" not in data:
        data["sort_order"] = _next_sort_order(
            db,
            chapter.subject_id,
            new_parent_id,
            exclude_id=chapter.id,
        )

    for field, value in data.items():
        setattr(chapter, field, value)

    db.commit()
    db.refresh(chapter)
    return _to_read(chapter)


def delete_chapter(
    db: Session,
    chapter_id: str,
    *,
    cascade: bool,
) -> None:
    chapter = _get_chapter_or_404(db, chapter_id)
    descendants = _descendant_ids(db, chapter.subject_id, chapter.id)

    if descendants and not cascade:
        raise DomainError(
            409,
            "chapter_has_children",
            f"该章节下仍有 {len(descendants)} 个子章节，请确认后再删除",
            descendant_count=len(descendants),
        )

    db.delete(chapter)
    db.commit()


def move_chapter(
    db: Session,
    chapter_id: str,
    direction: str,
) -> ChapterRead:
    chapter = _get_chapter_or_404(db, chapter_id)
    siblings = db.scalars(
        select(Chapter)
        .where(*_sibling_conditions(chapter.subject_id, chapter.parent_id))
        .order_by(Chapter.sort_order, Chapter.created_at, Chapter.id)
    ).all()

    for index, sibling in enumerate(siblings):
        sibling.sort_order = index * 10

    position = next(
        index for index, sibling in enumerate(siblings) if sibling.id == chapter.id
    )
    target = position - 1 if direction == "up" else position + 1
    if target < 0 or target >= len(siblings):
        raise DomainError(
            409,
            "cannot_move",
            "章节已经在当前层级的最前面或最后面",
        )

    siblings[position].sort_order, siblings[target].sort_order = (
        siblings[target].sort_order,
        siblings[position].sort_order,
    )
    db.commit()
    db.refresh(chapter)
    return _to_read(chapter)
