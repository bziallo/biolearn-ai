from pydantic import BaseModel, Field, SecretStr

from app.core.enums import KnowledgePointType


class AIDocumentAnalysis(BaseModel):
    theme: str = ""
    learning_objectives: list[str] = Field(default_factory=list)
    sections: list[str] = Field(default_factory=list)
    core_concepts: list[str] = Field(default_factory=list)
    processes: list[str] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)
    formulas: list[str] = Field(default_factory=list)
    confusions: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    cross_links: list[str] = Field(default_factory=list)


class AIKnowledgeDraft(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    type: KnowledgePointType
    explanation: str = Field(min_length=1, max_length=20000)
    core_points: list[str] = Field(default_factory=list, max_length=30)
    conditions: str | None = Field(default=None, max_length=4000)
    source_quote: str | None = Field(default=None, max_length=4000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    needs_review: bool = True
    parent_name: str | None = None


class AIExtractionResponse(BaseModel):
    points: list[AIKnowledgeDraft] = Field(default_factory=list, max_length=50)


class AIMergedPoint(BaseModel):
    ref: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=300)
    type: KnowledgePointType
    explanation: str = Field(min_length=1, max_length=20000)
    core_points: list[str] = Field(default_factory=list, max_length=30)
    conditions: str | None = Field(default=None, max_length=4000)
    parent_ref: str | None = None
    source_point_ids: list[int] = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    needs_review: bool = True
    conflict_note: str | None = Field(default=None, max_length=4000)


class AIMergeResponse(BaseModel):
    merged_points: list[AIMergedPoint] = Field(
        default_factory=list,
        max_length=500,
    )


class AIStatusResponse(BaseModel):
    configured: bool
    provider: str
    model: str
    api_base: str
    key_configured: bool
    source: str
    message: str


class AIProviderConfigRequest(BaseModel):
    provider: str = "openai-compatible"
    api_base: str | None = None
    model: str | None = None
    api_key: SecretStr | None = None
    clear_key: bool = False
    timeout_seconds: float | None = Field(default=None, ge=1)
    max_retries: int | None = Field(default=None, ge=0, le=10)
    temperature: float | None = Field(default=None, ge=0, le=2)


class AIConnectionTestResponse(BaseModel):
    ok: bool
    message: str
    model: str | None = None
