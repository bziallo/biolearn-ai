from app.core.enums import (
    KnowledgeOrigin,
    KnowledgePointType,
    ReviewStatus,
)
from app.models.document import DocumentChunk
from app.models.knowledge import KnowledgeExtractionJob, KnowledgePoint
from app.schemas.document import DocumentChunkRead
from app.schemas.knowledge import JobRead, KnowledgePointRead


def job_read(job: KnowledgeExtractionJob | None) -> JobRead | None:
    if job is None:
        return None
    return JobRead(
        id=job.id,
        document_id=job.document_id,
        status=job.status,
        stage=job.stage,
        progress=job.progress,
        error=job.error,
        cancel_requested=job.cancel_requested,
        attempts=job.attempts,
        provider=job.provider,
        model=job.model,
        total_chunks=job.total_chunks,
        processed_chunks=job.processed_chunks,
        extracted_count=job.extracted_count,
        merged_count=job.merged_count,
        duplicate_count=job.duplicate_count,
        timings=job.timings,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        updated_at=job.updated_at,
    )


def chunk_read(chunk: DocumentChunk) -> DocumentChunkRead:
    return DocumentChunkRead(
        id=chunk.id,
        chunk_index=chunk.chunk_index,
        heading_path=chunk.heading_path,
        heading_level=chunk.heading_level,
        content=chunk.content,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        slide_number=chunk.slide_number,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        location_label=chunk.location_label,
    )


def point_read(point: KnowledgePoint) -> KnowledgePointRead:
    return KnowledgePointRead(
        id=point.id,
        subject_id=point.subject_id,
        chapter_id=point.chapter_id,
        document_id=point.document_id,
        parent_id=point.parent_id,
        name=point.name,
        type=KnowledgePointType(point.point_type),
        explanation=point.explanation,
        core_points=list(point.core_points or []),
        conditions=point.conditions,
        source_quote=point.source_quote,
        source_quote_verified=point.source_quote_verified,
        source_page=point.source_page,
        source_page_end=point.source_page_end,
        source_slide=point.source_slide,
        source_locator=point.source_locator,
        source_chunk_id=point.source_chunk_id,
        importance=point.importance,
        prerequisites=list(point.prerequisites or []),
        external_id=point.external_id,
        confidence=point.confidence,
        review_note=point.review_note,
        needs_review=point.needs_review,
        origin=KnowledgeOrigin(point.origin),
        review_status=ReviewStatus(point.review_status),
        duplicate_of_id=point.duplicate_of_id,
        reviewed_at=point.reviewed_at,
        published_at=point.published_at,
        created_at=point.created_at,
        updated_at=point.updated_at,
    )
