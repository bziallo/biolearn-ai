from datetime import datetime

from pydantic import BaseModel


class DocumentChunkRead(BaseModel):
    id: str
    chunk_index: int
    heading_path: str | None
    heading_level: int | None
    content: str
    page_start: int | None
    page_end: int | None
    slide_number: int | None
    char_start: int
    char_end: int
    location_label: str


class DocumentRead(BaseModel):
    id: str
    subject_id: str
    chapter_id: str | None
    chapter_name: str | None
    name: str
    content_title: str | None
    original_filename: str
    mime_type: str
    extension: str
    size_bytes: int
    sha256: str
    status: str
    parse_error: str | None
    parse_warnings: str | None
    page_count: int | None
    slide_count: int | None
    chunk_count: int
    knowledge_point_count: int
    approved_count: int
    duplicate: bool = False
    uploaded_at: datetime
    parsed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DocumentUpdate(BaseModel):
    name: str | None = None
    subject_id: str | None = None
    chapter_id: str | None = None


class DocumentDetail(DocumentRead):
    chunks: list[DocumentChunkRead]
    latest_job: "JobRead | None"


from app.schemas.knowledge import JobRead  # noqa: E402

DocumentDetail.model_rebuild()
