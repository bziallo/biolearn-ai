from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.document import (
    DocumentChunkRead,
    DocumentDetail,
    DocumentRead,
    DocumentUpdate,
)
from app.schemas.knowledge import DocumentKnowledgeResponse, JobRead
from app.services import documents as document_service
from app.services import knowledge as knowledge_service
from app.services import knowledge_review
from app.services.mappers import chunk_read

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    subject_id: str = Form(..., min_length=1, max_length=64),
    chapter_id: str | None = Form(default=None),
    name: str | None = Form(default=None),
    force: bool = Form(default=False),
    db: Session = Depends(get_db),
) -> DocumentRead:
    document = await document_service.create_document_from_upload(
        db,
        file,
        subject_id=subject_id,
        chapter_id=chapter_id or None,
        name=name,
        force=force,
    )
    background_tasks.add_task(document_service.process_document, document.id)
    return document


@router.get("", response_model=list[DocumentRead])
def list_documents(
    subject_id: str | None = Query(default=None),
    chapter_id: str | None = Query(default=None),
    document_status: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[DocumentRead]:
    return document_service.list_documents(
        db,
        subject_id=subject_id,
        chapter_id=chapter_id,
        status=document_status,
    )


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
) -> DocumentDetail:
    return document_service.get_document_detail(db, document_id)


@router.patch("/{document_id}", response_model=DocumentRead)
def update_document(
    document_id: str,
    payload: DocumentUpdate,
    db: Session = Depends(get_db),
) -> DocumentRead:
    return document_service.update_document(db, document_id, payload)


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkRead])
def get_document_chunks(
    document_id: str,
    db: Session = Depends(get_db),
) -> list[DocumentChunkRead]:
    detail = document_service.get_document_detail(db, document_id)
    return detail.chunks


@router.post("/{document_id}/retry-parse", response_model=DocumentRead)
def retry_parse(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> DocumentRead:
    document = document_service.reset_document_for_parse(db, document_id)
    background_tasks.add_task(document_service.process_document, document_id)
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    cascade: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> Response:
    document_service.delete_document(db, document_id, cascade=cascade)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{document_id}/extract", response_model=JobRead)
def extract_knowledge(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> JobRead:
    job = knowledge_service.create_extraction_job(db, document_id)
    background_tasks.add_task(knowledge_service.run_extraction, job.id)
    return job


@router.get("/{document_id}/jobs", response_model=list[JobRead])
def list_document_jobs(
    document_id: str,
    db: Session = Depends(get_db),
) -> list[JobRead]:
    return knowledge_service.list_jobs(db, document_id)


@router.get("/{document_id}/knowledge-points", response_model=DocumentKnowledgeResponse)
def get_document_knowledge(
    document_id: str,
    db: Session = Depends(get_db),
) -> DocumentKnowledgeResponse:
    return knowledge_review.get_document_knowledge(db, document_id)
