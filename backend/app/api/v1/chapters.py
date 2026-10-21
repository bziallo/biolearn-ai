from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.chapter import (
    ChapterDetail,
    ChapterMove,
    ChapterRead,
    ChapterUpdate,
)
from app.services import chapters as chapter_service

router = APIRouter(prefix="/chapters", tags=["chapters"])

ChapterId = Annotated[str, Path(min_length=1, max_length=64)]


@router.get("/{chapter_id}", response_model=ChapterDetail)
def get_chapter(
    chapter_id: ChapterId,
    db: Session = Depends(get_db),
) -> ChapterDetail:
    return chapter_service.get_chapter_detail(db, chapter_id)


@router.patch("/{chapter_id}", response_model=ChapterRead)
def update_chapter(
    chapter_id: ChapterId,
    payload: ChapterUpdate,
    db: Session = Depends(get_db),
) -> ChapterRead:
    return chapter_service.update_chapter(db, chapter_id, payload)


@router.delete("/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chapter(
    chapter_id: ChapterId,
    cascade: bool = Query(
        default=False,
        description="确认级联删除该章节及其全部子章节",
    ),
    db: Session = Depends(get_db),
) -> Response:
    chapter_service.delete_chapter(db, chapter_id, cascade=cascade)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{chapter_id}/move", response_model=ChapterRead)
def move_chapter(
    chapter_id: ChapterId,
    payload: ChapterMove,
    db: Session = Depends(get_db),
) -> ChapterRead:
    return chapter_service.move_chapter(db, chapter_id, payload.direction)
