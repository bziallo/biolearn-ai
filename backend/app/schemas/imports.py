from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ImportMode = Literal["preset", "auto_create", "smart_archive"]
UncertainPolicy = Literal["confirm", "use_default", "create"]
SuggestedAction = Literal["create", "reuse", "uncertain"]


class ImportPreferencesRead(BaseModel):
    default_subject_id: str | None
    default_subject_name: str | None
    default_chapter_id: str | None
    default_chapter_name: str | None
    default_mode: ImportMode
    auto_analyze: bool
    require_preview: bool
    uncertain_policy: UncertainPolicy
    updated_at: datetime | None


class ImportPreferencesUpdate(BaseModel):
    default_subject_id: str | None = None
    default_chapter_id: str | None = None
    default_mode: ImportMode = "preset"
    auto_analyze: bool = True
    require_preview: bool = True
    uncertain_policy: UncertainPolicy = "confirm"


class SuggestedChapter(BaseModel):
    name: str
    level: int = Field(ge=1, le=12)
    parent_index: int | None = None
    action: SuggestedAction = "create"
    existing_chapter_id: str | None = None
    existing_path: str | None = None
    confidence: float = Field(ge=0, le=1)
    source_slide: int | None = None
    source_kind: str = "unknown"
    reason: str | None = None


class ExternalPointPreview(BaseModel):
    point_id: str | None = None
    title: str
    chapter_path: list[str] = Field(default_factory=list)
    category: str
    importance: str | None = None
    source_page: int | None = None
    source_slide: int | None = None
    duplicate_of_id: str | None = None
    duplicate_of_title: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ImportSuggestion(BaseModel):
    title: str
    subject_id: str
    subject_name: str
    subject_confidence: float = Field(ge=0, le=1)
    subject_reason: str | None = None
    outline_source: str
    chapters: list[SuggestedChapter] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    needs_confirmation: bool = True
    reasons: list[str] = Field(default_factory=list)
    source_type: str = "courseware"
    knowledge_point_count: int = 0
    duplicate_point_count: int = 0
    missing_source_count: int = 0
    points_preview: list[ExternalPointPreview] = Field(default_factory=list)
    duplicate_import: bool = False


class ImportResult(BaseModel):
    subject_id: str
    chapter_id: str | None
    chapter_name: str | None
    created_chapter_ids: list[str] = Field(default_factory=list)
    reused_chapter_ids: list[str] = Field(default_factory=list)
    chapter_path: list[str] = Field(default_factory=list)
    duplicate: bool = False
    knowledge_point_count: int = 0
    created_point_count: int = 0
    updated_point_count: int = 0
    skipped_point_count: int = 0
    warning_count: int = 0


class ImportRead(BaseModel):
    id: str
    document_id: str
    document_name: str
    document_status: str
    status: str
    stage: str
    progress: int
    mode: ImportMode
    source_type: str = "courseware"
    duplicate_strategy: str | None = None
    auto_analyze: bool
    require_preview: bool
    uncertain_policy: UncertainPolicy
    suggestion: ImportSuggestion | None
    result: ImportResult | None
    error: str | None
    analysis_job_id: str | None
    analysis_status: str
    analysis_error: str | None
    timings: dict[str, object] | None = None
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None


class ImportConfirmRequest(BaseModel):
    accept_suggestions: bool = False
    subject_id: str | None = None
    chapter_id: str | None = None
    create_missing: bool = True
    auto_analyze: bool | None = None
