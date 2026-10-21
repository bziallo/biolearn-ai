from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.core.enums import DocumentStatus, JobStatus, QuestionJobStatus
from app.db.base import utc_now
from app.db.session import SessionLocal
from app.models import (
    Document,
    ImportJob,
    KnowledgeExtractionJob,
    QuestionGenerationJob,
)


def recover_interrupted_tasks(
    session_factory: Callable[[], Session] = SessionLocal,
) -> None:
    """Mark tasks interrupted by a process restart as retryable failures."""

    with session_factory() as db:
        inspector = inspect(db.get_bind())
        if not (
            inspector.has_table("documents")
            and inspector.has_table("knowledge_extraction_jobs")
        ):
            return
        documents = db.scalars(
            select(Document).where(Document.status == DocumentStatus.PARSING.value)
        ).all()
        for document in documents:
            document.status = DocumentStatus.FAILED.value
            document.parse_error = "解析任务被服务重启中断，请点击重试"
            document.parsed_at = utc_now()

        jobs = db.scalars(
            select(KnowledgeExtractionJob).where(
                KnowledgeExtractionJob.status.in_(
                    [
                        JobStatus.QUEUED.value,
                        JobStatus.ANALYZING.value,
                        JobStatus.EXTRACTING.value,
                        JobStatus.MERGING.value,
                        JobStatus.CANCELLING.value,
                    ]
                )
            )
        ).all()
        for job in jobs:
            if job.status == JobStatus.CANCELLING.value or job.cancel_requested:
                job.status = JobStatus.CANCELLED.value
                job.stage = "已停止（服务重启中断）"
                job.error = None
            else:
                job.status = JobStatus.FAILED.value
                job.stage = "服务重启中断"
                job.error = "AI 任务被服务重启中断，请点击重试"
            job.finished_at = utc_now()

        import_jobs = db.scalars(
            select(ImportJob).where(
                ImportJob.status.in_(
                    ["queued", "parsing", "detecting", "archiving", "analyzing"]
                )
            )
        ).all() if inspector.has_table("import_jobs") else []
        for import_job in import_jobs:
            if import_job.status == "analyzing":
                # The import itself already committed; only the AI phase was
                # interrupted, so never roll back the document or chapters.
                import_job.status = "completed"
                import_job.stage = "资料已归档，AI 分析在服务重启时中断"
                import_job.analysis_status = "failed"
                import_job.analysis_error = "AI 分析被服务重启中断"
                import_job.progress = 100
            else:
                import_job.status = "failed"
                import_job.stage = "导入失败"
                import_job.error = "导入被服务重启中断，请点击重试"
            import_job.finished_at = utc_now()

        if inspector.has_table("question_generation_jobs"):
            question_jobs = db.scalars(
                select(QuestionGenerationJob).where(
                    QuestionGenerationJob.status.in_(
                        [
                            QuestionJobStatus.QUEUED.value,
                            QuestionJobStatus.RUNNING.value,
                            QuestionJobStatus.CANCELLING.value,
                        ]
                    )
                )
            ).all()
            for question_job in question_jobs:
                if (
                    question_job.status == QuestionJobStatus.CANCELLING.value
                    or question_job.cancel_requested
                ):
                    question_job.status = QuestionJobStatus.CANCELLED.value
                    question_job.stage = "已停止（服务重启中断）"
                    question_job.error = None
                else:
                    question_job.status = QuestionJobStatus.FAILED.value
                    question_job.stage = "服务重启中断"
                    question_job.error = "出题任务被服务重启中断，请点击重试"
                question_job.finished_at = utc_now()

        db.commit()
