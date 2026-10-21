from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
)

from app.core.enums import (
    JobStatus,
    KnowledgeOrigin,
    KnowledgePointType,
    ReviewStatus,
)

PointName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=300),
]
PointExplanation = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20000),
]
PointCondition = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=4000),
]


class JobRead(BaseModel):
    id: str
    document_id: str
    status: str
    stage: str
    progress: int
    error: str | None
    cancel_requested: bool = False
    attempts: int
    provider: str
    model: str
    total_chunks: int
    processed_chunks: int
    extracted_count: int
    merged_count: int
    duplicate_count: int
    timings: dict[str, object] | None = None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime


class KnowledgePointRead(BaseModel):
    id: str
    subject_id: str
    chapter_id: str | None
    document_id: str
    parent_id: str | None
    name: str
    type: KnowledgePointType
    explanation: str
    core_points: list[str]
    conditions: str | None
    source_quote: str | None
    source_quote_verified: bool
    source_page: int | None
    source_page_end: int | None
    source_slide: int | None
    source_locator: str | None
    source_chunk_id: str | None
    importance: str | None = None
    prerequisites: list[str] = Field(default_factory=list)
    external_id: str | None = None
    confidence: float | None
    review_note: str | None
    needs_review: bool
    origin: KnowledgeOrigin
    review_status: ReviewStatus
    duplicate_of_id: str | None
    reviewed_at: datetime | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class KnowledgePointTreeNode(KnowledgePointRead):
    children: list[KnowledgePointTreeNode] = Field(default_factory=list)


class KnowledgePointDetail(KnowledgePointRead):
    document_name: str
    subject_name: str
    chapter_name: str | None
    source_chunk_content: str | None
    source_chunk_heading: str | None


class KnowledgeReviewStats(BaseModel):
    total: int
    pending: int
    approved: int
    needs_revision: int
    ignored: int
    needs_review: int
    duplicates: int
    failed_jobs: int


class DocumentBrief(BaseModel):
    id: str
    name: str
    status: str
    chunk_count: int


class DocumentKnowledgeResponse(BaseModel):
    document: DocumentBrief
    stats: KnowledgeReviewStats
    points: list[KnowledgePointTreeNode]
    latest_job: JobRead | None


class KnowledgePointCreate(BaseModel):
    document_id: str
    parent_id: str | None = None
    name: PointName
    type: KnowledgePointType = KnowledgePointType.BASIC_CONCEPT
    explanation: PointExplanation
    core_points: list[str] = Field(default_factory=list, max_length=30)
    conditions: PointCondition | None = None
    review_note: str | None = None


class KnowledgePointUpdate(BaseModel):
    name: PointName | None = None
    type: KnowledgePointType | None = None
    explanation: PointExplanation | None = None
    core_points: list[str] | None = Field(default=None, max_length=30)
    conditions: PointCondition | None = None
    review_note: str | None = None
    parent_id: str | None = None


class KnowledgeReviewRequest(BaseModel):
    status: ReviewStatus


class KnowledgeBulkReviewRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=500)
    status: ReviewStatus


class KnowledgeMergeRequest(BaseModel):
    source_ids: list[str] = Field(min_length=2, max_length=50)
    name: PointName | None = None
    explanation: PointExplanation | None = None


class KnowledgeListResponse(BaseModel):
    points: list[KnowledgePointRead]
    stats: KnowledgeReviewStats
    total: int = 0


KnowledgePointTreeNode.model_rebuild()
