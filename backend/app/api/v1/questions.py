from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.question import (
    QuestionBulkReviewRequest,
    QuestionCreate,
    QuestionGenerateRequest,
    QuestionGenerationJobRead,
    QuestionListResponse,
    QuestionRead,
    QuestionRegenerateRequest,
    QuestionReviewRequest,
    QuestionUpdate,
)
from app.services import question_generation
from app.services import questions as question_service

router = APIRouter(prefix="/questions", tags=["questions"])


@router.get("", response_model=QuestionListResponse)
def list_questions(
    subject_id: str | None = Query(default=None),
    chapter_id: str | None = Query(default=None),
    knowledge_point_id: str | None = Query(default=None),
    type: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    status: str | None = Query(default=None),
    origin: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> QuestionListResponse:
    return question_service.list_questions(
        db,
        subject_id=subject_id,
        chapter_id=chapter_id,
        knowledge_point_id=knowledge_point_id,
        question_type=type,
        difficulty=difficulty,
        status=status,
        origin=origin,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=QuestionRead, status_code=status.HTTP_201_CREATED)
def create_question(
    payload: QuestionCreate,
    db: Session = Depends(get_db),
) -> QuestionRead:
    return question_service.create_question(db, payload)


@router.post("/generate", response_model=QuestionGenerationJobRead)
def generate_questions(
    payload: QuestionGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> QuestionGenerationJobRead:
    job = question_generation.create_generation_job(
        db,
        subject_id=payload.subject_id,
        chapter_id=payload.chapter_id,
        knowledge_point_ids=payload.knowledge_point_ids,
        types=payload.types,
        count=payload.count,
        difficulty=payload.difficulty,
    )
    background_tasks.add_task(question_generation.run_generation, job.id)
    return question_generation.get_generation_job(db, job.id)


@router.get(
    "/generation-jobs/{job_id}",
    response_model=QuestionGenerationJobRead,
)
def get_generation_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> QuestionGenerationJobRead:
    return question_generation.get_generation_job(db, job_id)


@router.post(
    "/generation-jobs/{job_id}/retry",
    response_model=QuestionGenerationJobRead,
)
def retry_generation_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> QuestionGenerationJobRead:
    job = question_generation.retry_generation_job(db, job_id)
    background_tasks.add_task(question_generation.run_generation, job.id)
    return question_generation.get_generation_job(db, job.id)


@router.post(
    "/generation-jobs/{job_id}/cancel",
    response_model=QuestionGenerationJobRead,
)
def cancel_generation_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> QuestionGenerationJobRead:
    return question_generation.cancel_generation_job(db, job_id)


@router.post("/bulk-review")
def bulk_review(
    payload: QuestionBulkReviewRequest,
    db: Session = Depends(get_db),
) -> dict[str, int]:
    return {
        "updated": question_service.bulk_review(
            db,
            payload.ids,
            payload.status,
            payload.note,
        )
    }


@router.post("/{question_id}/regenerate", response_model=QuestionGenerationJobRead)
def regenerate_question(
    question_id: str,
    payload: QuestionRegenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> QuestionGenerationJobRead:
    job = question_service.regenerate_question(
        db,
        question_id,
        count=payload.count,
        difficulty=payload.difficulty,
    )
    background_tasks.add_task(question_generation.run_generation, job.id)
    return question_generation.get_generation_job(db, job.id)


@router.get("/{question_id}", response_model=QuestionRead)
def get_question(
    question_id: str,
    db: Session = Depends(get_db),
) -> QuestionRead:
    return question_service.get_question(db, question_id)


@router.patch("/{question_id}", response_model=QuestionRead)
def update_question(
    question_id: str,
    payload: QuestionUpdate,
    db: Session = Depends(get_db),
) -> QuestionRead:
    return question_service.update_question(db, question_id, payload)


@router.post("/{question_id}/review", response_model=QuestionRead)
def review_question(
    question_id: str,
    payload: QuestionReviewRequest,
    db: Session = Depends(get_db),
) -> QuestionRead:
    return question_service.review_question(
        db,
        question_id,
        payload.status,
        payload.note,
    )
