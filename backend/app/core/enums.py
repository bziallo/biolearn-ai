from enum import Enum


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"
    NEEDS_OCR = "needs_ocr"


class JobStatus(str, Enum):
    QUEUED = "queued"
    ANALYZING = "analyzing"
    EXTRACTING = "extracting"
    MERGING = "merging"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"
    IGNORED = "ignored"


class KnowledgeOrigin(str, Enum):
    AI = "ai"
    MANUAL = "manual"


class KnowledgePointType(str, Enum):
    BASIC_CONCEPT = "basic_concept"
    STRUCTURE = "structure"
    CLASSIFICATION = "classification"
    MECHANISM = "mechanism"
    PROCESS = "process"
    CAUSALITY = "causality"
    FORMULA = "formula"
    EXPERIMENT = "experiment"
    APPLICATION = "application"
    COMPARISON = "comparison"


class QuestionType(str, Enum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"


class QuestionDifficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class QuestionOrigin(str, Enum):
    AI = "ai"
    MANUAL = "manual"


class QuestionJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class GradingMode(str, Enum):
    CHOICE_EXACT = "choice_exact"
    BOOLEAN_EXACT = "boolean_exact"
    MANUAL = "manual"


class PracticeStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
