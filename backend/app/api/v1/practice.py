from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.question import (
    ManualGradeRequest,
    PracticeResult,
    PracticeSessionRead,
    PracticeStartRequest,
    PracticeSubmitRequest,
    WrongQuestionRead,
)
from app.services import practice as practice_service

router = APIRouter(prefix="/practice", tags=["practice"])


@router.post("/sessions", response_model=PracticeSessionRead)
def start_session(
    payload: PracticeStartRequest,
    db: Session = Depends(get_db),
) -> PracticeSessionRead:
    return practice_service.start_session(db, payload)


@router.get("/sessions", response_model=list[PracticeSessionRead])
def list_sessions(
    subject_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[PracticeSessionRead]:
    return practice_service.list_sessions(db, subject_id=subject_id, limit=limit)


@router.get("/wrong-questions", response_model=list[WrongQuestionRead])
def wrong_questions(
    subject_id: str = Query(...),
    chapter_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[WrongQuestionRead]:
    return practice_service.wrong_questions(
        db,
        subject_id=subject_id,
        chapter_id=chapter_id,
        limit=limit,
    )


@router.get("/sessions/{session_id}", response_model=PracticeSessionRead)
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> PracticeSessionRead:
    return practice_service.get_session(db, session_id)


@router.post("/sessions/{session_id}/submit", response_model=PracticeResult)
def submit_answers(
    session_id: str,
    payload: PracticeSubmitRequest,
    db: Session = Depends(get_db),
) -> PracticeResult:
    return practice_service.submit_answers(db, session_id, payload)


@router.get("/sessions/{session_id}/result", response_model=PracticeResult)
def get_result(
    session_id: str,
    db: Session = Depends(get_db),
) -> PracticeResult:
    return practice_service.get_result(db, session_id)


@router.post("/answers/{answer_id}/grade", response_model=PracticeResult)
def grade_answer(
    answer_id: str,
    payload: ManualGradeRequest,
    db: Session = Depends(get_db),
) -> PracticeResult:
    return practice_service.manual_grade(db, answer_id, payload)
