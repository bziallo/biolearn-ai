from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.chapter import ChapterCreate, ChapterRead, ChapterTreeNode
from app.schemas.subject import SubjectCreate, SubjectRead, SubjectUpdate
from app.services import chapters as chapter_service
from app.services import subjects as subject_service

router = APIRouter(prefix="/subjects", tags=["subjects"])

SubjectId = Annotated[str, Path(min_length=1, max_length=64)]


@router.get("", response_model=list[SubjectRead])
def list_subjects(db: Session = Depends(get_db)) -> list[SubjectRead]:
    return subject_service.list_subjects(db)


@router.post("", response_model=SubjectRead, status_code=status.HTTP_201_CREATED)
def create_subject(
    payload: SubjectCreate,
    db: Session = Depends(get_db),
) -> SubjectRead:
    return subject_service.create_subject(db, payload)


@router.get("/{subject_id}/chapters", response_model=list[ChapterTreeNode])
def list_subject_chapters(
    subject_id: SubjectId,
    db: Session = Depends(get_db),
) -> list[ChapterTreeNode]:
    return chapter_service.list_chapter_tree(db, subject_id)


@router.post(
    "/{subject_id}/chapters",
    response_model=ChapterRead,
    status_code=status.HTTP_201_CREATED,
)
def create_subject_chapter(
    subject_id: SubjectId,
    payload: ChapterCreate,
    db: Session = Depends(get_db),
) -> ChapterRead:
    return chapter_service.create_chapter(db, subject_id, payload)


@router.get("/{subject_id}", response_model=SubjectRead)
def get_subject(
    subject_id: SubjectId,
    db: Session = Depends(get_db),
) -> SubjectRead:
    return subject_service.get_subject(db, subject_id)


@router.patch("/{subject_id}", response_model=SubjectRead)
def update_subject(
    subject_id: SubjectId,
    payload: SubjectUpdate,
    db: Session = Depends(get_db),
) -> SubjectRead:
    return subject_service.update_subject(db, subject_id, payload)


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(
    subject_id: SubjectId,
    cascade: bool = Query(
        default=False,
        description="确认级联删除该学科下的全部章节",
    ),
    db: Session = Depends(get_db),
) -> Response:
    subject_service.delete_subject(db, subject_id, cascade=cascade)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
