from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.enums import (
    QuestionDifficulty,
    QuestionJobStatus,
    QuestionOrigin,
    QuestionStatus,
    QuestionType,
)


class QuestionOption(BaseModel):
    key: str = Field(min_length=1, max_length=12)
    text: str = Field(min_length=1, max_length=500)


class QuestionKnowledgePointBrief(BaseModel):
    id: str
    name: str
    chapter_id: str | None = None
    document_id: str
    source_page: int | None = None
    source_slide: int | None = None
    source_locator: str | None = None
    review_status: str


class QuestionRead(BaseModel):
    id: str
    subject_id: str
    subject_name: str
    chapter_id: str | None
    chapter_name: str | None
    source_document_id: str | None
    source_document_name: str | None
    generation_job_id: str | None
    duplicate_of_id: str | None
    duplicate_reason: str | None
    type: QuestionType
    stem: str
    options: list[QuestionOption]
    answer: dict[str, Any]
    grading_rule: dict[str, Any]
    explanation: str
    difficulty: QuestionDifficulty
    status: QuestionStatus
    origin: QuestionOrigin
    source_locator: str | None
    ai_provider: str
    ai_model: str
    confidence: float | None
    review_note: str | None
    score: float
    knowledge_points: list[QuestionKnowledgePointBrief]
    reviewed_at: datetime | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class QuestionStats(BaseModel):
    total: int = 0
    pending: int = 0
    approved: int = 0
    rejected: int = 0
    needs_revision: int = 0


class QuestionListResponse(BaseModel):
    questions: list[QuestionRead]
    total: int
    stats: QuestionStats


class QuestionCreate(BaseModel):
    subject_id: str
    chapter_id: str | None = None
    knowledge_point_ids: list[str] = Field(min_length=1, max_length=20)
    type: QuestionType
    stem: str = Field(min_length=5, max_length=2000)
    options: list[QuestionOption] = Field(default_factory=list, max_length=8)
    answer: dict[str, Any] = Field(default_factory=dict)
    explanation: str = Field(min_length=5, max_length=8000)
    difficulty: QuestionDifficulty = QuestionDifficulty.MEDIUM
    source_locator: str | None = Field(default=None, max_length=300)
    review_note: str | None = Field(default=None, max_length=2000)


class QuestionUpdate(BaseModel):
    chapter_id: str | None = None
    knowledge_point_ids: list[str] | None = Field(default=None, min_length=1, max_length=20)
    type: QuestionType | None = None
    stem: str | None = Field(default=None, min_length=5, max_length=2000)
    options: list[QuestionOption] | None = Field(default=None, max_length=8)
    answer: dict[str, Any] | None = None
    explanation: str | None = Field(default=None, min_length=5, max_length=8000)
    difficulty: QuestionDifficulty | None = None
    source_locator: str | None = Field(default=None, max_length=300)
    review_note: str | None = Field(default=None, max_length=2000)


class QuestionReviewRequest(BaseModel):
    status: QuestionStatus
    note: str | None = Field(default=None, max_length=2000)


class QuestionBulkReviewRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=200)
    status: QuestionStatus
    note: str | None = Field(default=None, max_length=2000)


class QuestionGenerateRequest(BaseModel):
    subject_id: str
    chapter_id: str | None = None
    knowledge_point_ids: list[str] = Field(default_factory=list, max_length=30)
    types: list[QuestionType] = Field(
        default_factory=lambda: [
            QuestionType.SINGLE_CHOICE,
            QuestionType.MULTIPLE_CHOICE,
            QuestionType.TRUE_FALSE,
        ],
        min_length=1,
        max_length=4,
    )
    count: int = Field(default=5, ge=1, le=20)
    difficulty: QuestionDifficulty | None = None


class QuestionRegenerateRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=5)
    difficulty: QuestionDifficulty | None = None


class QuestionGenerationJobRead(BaseModel):
    id: str
    subject_id: str
    chapter_id: str | None
    status: QuestionJobStatus
    stage: str
    progress: int
    error: str | None
    cancel_requested: bool
    attempts: int
    provider: str
    model: str
    request: dict[str, Any]
    generated_count: int
    skipped_count: int
    timings: dict[str, Any] | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime


class GeneratedQuestionDraft(BaseModel):
    type: QuestionType
    stem: str = Field(min_length=5, max_length=2000)
    options: list[QuestionOption] = Field(default_factory=list, max_length=8)
    answer: dict[str, Any] = Field(default_factory=dict)
    explanation: str = Field(min_length=5, max_length=8000)
    difficulty: QuestionDifficulty = QuestionDifficulty.MEDIUM
    knowledge_point_ids: list[str] = Field(min_length=1, max_length=10)
    confidence: float | None = Field(default=None, ge=0, le=1)


class GeneratedQuestionBatch(BaseModel):
    questions: list[GeneratedQuestionDraft] = Field(default_factory=list, max_length=20)


class PracticeStartRequest(BaseModel):
    subject_id: str
    chapter_id: str | None = None
    knowledge_point_ids: list[str] = Field(default_factory=list, max_length=50)
    types: list[QuestionType] = Field(default_factory=list, max_length=4)
    difficulty: QuestionDifficulty | None = None
    count: int = Field(default=10, ge=1, le=50)
    wrong_only: bool = False


class PracticeQuestion(BaseModel):
    id: str
    type: QuestionType
    stem: str
    options: list[QuestionOption]
    difficulty: QuestionDifficulty
    chapter_id: str | None
    knowledge_points: list[QuestionKnowledgePointBrief]


class PracticeSessionRead(BaseModel):
    id: str
    subject_id: str
    subject_name: str
    chapter_id: str | None
    chapter_name: str | None
    status: str
    total_questions: int
    answered_count: int
    correct_count: int
    pending_manual_count: int
    score: float | None
    started_at: datetime
    finished_at: datetime | None
    questions: list[PracticeQuestion] = Field(default_factory=list)


class PracticeAnswerInput(BaseModel):
    question_id: str
    user_answer: dict[str, Any] = Field(default_factory=dict)


class PracticeSubmitRequest(BaseModel):
    answers: list[PracticeAnswerInput] = Field(min_length=1, max_length=50)


class PracticeAnswerResult(BaseModel):
    id: str
    question: QuestionRead
    user_answer: dict[str, Any]
    is_correct: bool | None
    score: float | None
    max_score: float
    feedback: str | None
    graded_by: str
    answered_at: datetime


class PracticeResult(BaseModel):
    session: PracticeSessionRead
    answers: list[PracticeAnswerResult]


class ManualGradeRequest(BaseModel):
    score: float = Field(ge=0, le=1)
    feedback: str | None = Field(default=None, max_length=4000)


class WrongQuestionRead(BaseModel):
    question: QuestionRead
    wrong_count: int
    last_answer: dict[str, Any]
    last_answered_at: datetime
