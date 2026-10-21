from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.knowledge import (
    JobRead,
    KnowledgeBulkReviewRequest,
    KnowledgeListResponse,
    KnowledgeMergeRequest,
    KnowledgePointCreate,
    KnowledgePointDetail,
    KnowledgePointUpdate,
    KnowledgeReviewRequest,
)
from app.services import knowledge as knowledge_service
from app.services import knowledge_review
from app.services.mappers import job_read

points_router = APIRouter(prefix="/knowledge-points", tags=["knowledge"])
jobs_router = APIRouter(prefix="/knowledge-jobs", tags=["knowledge"])


@points_router.get("", response_model=KnowledgeListResponse)
def list_points(
    document_id: str | None = Query(default=None),
    subject_id: str | None = Query(default=None),
    chapter_id: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    point_type: str | None = Query(default=None),
    origin: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=120),
    needs_review: bool | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> KnowledgeListResponse:
    return knowledge_review.list_knowledge_points(
        db,
        document_id=document_id,
        subject_id=subject_id,
        chapter_id=chapter_id,
        review_status=review_status,
        point_type=point_type,
        origin=origin,
        q=q,
        needs_review=needs_review,
        limit=limit,
        offset=offset,
    )


@points_router.post("", response_model=KnowledgePointDetail, status_code=status.HTTP_201_CREATED)
def create_point(
    payload: KnowledgePointCreate,
    db: Session = Depends(get_db),
) -> KnowledgePointDetail:
    return knowledge_review.create_manual_point(db, payload)


@points_router.post("/bulk-review")
def bulk_review(
    payload: KnowledgeBulkReviewRequest,
    db: Session = Depends(get_db),
) -> dict[str, int]:
    return {"updated": knowledge_review.bulk_review(db, payload)}


@points_router.post("/merge", response_model=KnowledgePointDetail)
def merge_points(
    payload: KnowledgeMergeRequest,
    db: Session = Depends(get_db),
) -> KnowledgePointDetail:
    return knowledge_review.merge_points(db, payload)


@points_router.get("/{point_id}", response_model=KnowledgePointDetail)
def get_point(
    point_id: str,
    db: Session = Depends(get_db),
) -> KnowledgePointDetail:
    return knowledge_review.get_point_detail(db, point_id)


@points_router.patch("/{point_id}", response_model=KnowledgePointDetail)
def update_point(
    point_id: str,
    payload: KnowledgePointUpdate,
    db: Session = Depends(get_db),
) -> KnowledgePointDetail:
    return knowledge_review.update_point(db, point_id, payload)


@points_router.delete("/{point_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_point(
    point_id: str,
    cascade: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> Response:
    knowledge_review.delete_point(db, point_id, cascade=cascade)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@points_router.post("/{point_id}/review", response_model=KnowledgePointDetail)
def review_point(
    point_id: str,
    payload: KnowledgeReviewRequest,
    db: Session = Depends(get_db),
) -> KnowledgePointDetail:
    return knowledge_review.review_point(db, point_id, payload.status)


@jobs_router.get("/{job_id}", response_model=JobRead)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> JobRead:
    job = knowledge_service.get_job_or_404(db, job_id)
    read = job_read(job)
    assert read is not None
    return read


@jobs_router.post("/{job_id}/retry", response_model=JobRead)
def retry_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> JobRead:
    job = knowledge_service.retry_extraction(db, job_id)
    background_tasks.add_task(knowledge_service.run_extraction, job.id)
    return job


@jobs_router.post("/{job_id}/cancel", response_model=JobRead)
def cancel_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> JobRead:
    return knowledge_service.cancel_extraction_job(db, job_id)
