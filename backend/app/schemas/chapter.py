from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
)

from app.schemas.subject import SubjectSummary

ChapterName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=160),
]
ChapterDescription = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=4000),
]
EntityId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]


class ChapterCreate(BaseModel):
    name: ChapterName
    description: ChapterDescription = ""
    parent_id: EntityId | None = None
    sort_order: int | None = Field(default=None, ge=0, le=1_000_000)


class ChapterUpdate(BaseModel):
    name: ChapterName | None = None
    description: ChapterDescription | None = None
    parent_id: EntityId | None = None
    sort_order: int | None = Field(default=None, ge=0, le=1_000_000)


class ChapterMove(BaseModel):
    direction: Literal["up", "down"]


class ChapterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    subject_id: str
    parent_id: str | None
    name: str
    description: str
    sort_order: int
    source_document_id: str | None = None
    source_import_job_id: str | None = None
    source_slide: int | None = None
    created_at: datetime
    updated_at: datetime


class ChapterTreeNode(ChapterRead):
    children: list[ChapterTreeNode] = Field(default_factory=list)


class ChapterPathItem(BaseModel):
    id: str
    name: str


class ChapterParentSummary(BaseModel):
    id: str
    name: str


class ChapterDetail(ChapterRead):
    subject: SubjectSummary
    parent: ChapterParentSummary | None
    path: list[ChapterPathItem]
    descendant_count: int


ChapterTreeNode.model_rebuild()
