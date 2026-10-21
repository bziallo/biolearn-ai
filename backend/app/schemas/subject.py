from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
)

SubjectName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]
SubjectDescription = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=4000),
]
SubjectColor = Annotated[
    str,
    StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$"),
]
SubjectIcon = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=32),
]


def _blank_optional_text_to_none(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


OptionalSubjectColor = Annotated[
    SubjectColor | None,
    BeforeValidator(_blank_optional_text_to_none),
]
OptionalSubjectIcon = Annotated[
    SubjectIcon | None,
    BeforeValidator(_blank_optional_text_to_none),
]


class SubjectCreate(BaseModel):
    name: SubjectName
    description: SubjectDescription = ""
    color: OptionalSubjectColor = None
    icon: OptionalSubjectIcon = None
    sort_order: int | None = Field(default=None, ge=0, le=1_000_000)


class SubjectUpdate(BaseModel):
    name: SubjectName | None = None
    description: SubjectDescription | None = None
    color: OptionalSubjectColor = None
    icon: OptionalSubjectIcon = None
    sort_order: int | None = Field(default=None, ge=0, le=1_000_000)


class SubjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    color: str | None
    icon: str | None
    sort_order: int
    chapter_count: int
    created_at: datetime
    updated_at: datetime


class SubjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    color: str | None
    icon: str | None
