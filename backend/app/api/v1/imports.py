from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.imports import (
    ImportConfirmRequest,
    ImportPreferencesRead,
    ImportPreferencesUpdate,
    ImportRead,
)
from app.core.errors import DomainError
from app.db.base import utc_now
from app.services import importing as import_service
from app.services import external_import as external_service

router = APIRouter(prefix="/imports", tags=["imports"])


@router.get("/preferences", response_model=ImportPreferencesRead)
def get_preferences(
    db: Session = Depends(get_db),
) -> ImportPreferencesRead:
    return import_service.preferences_read(db)


@router.put("/preferences", response_model=ImportPreferencesRead)
def update_preferences(
    payload: ImportPreferencesUpdate,
    db: Session = Depends(get_db),
) -> ImportPreferencesRead:
    return import_service.save_preferences(db, payload)


@router.get("", response_model=list[ImportRead])
def list_imports(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[ImportRead]:
    return import_service.list_imports(db, limit)


@router.post("", response_model=ImportRead, status_code=status.HTTP_201_CREATED)
async def create_import(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    subject_id: str | None = Form(default=None),
    chapter_id: str | None = Form(default=None),
    name: str | None = Form(default=None),
    mode: str | None = Form(default=None),
    auto_analyze: bool | None = Form(default=None),
    require_preview: bool | None = Form(default=None),
    uncertain_policy: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> ImportRead:
    result = await import_service.create_import(
        db,
        file,
        subject_id=subject_id or None,
        chapter_id=chapter_id or None,
        name=name,
        mode=mode,
        auto_analyze=auto_analyze,
        require_preview=require_preview,
        uncertain_policy=uncertain_policy,
    )
    if result.status == "queued":
        background_tasks.add_task(import_service.run_import, result.id)
    return result


@router.get("/external/template")
def get_external_template() -> dict:
    return external_service.external_template()


@router.post("/external", response_model=ImportRead, status_code=status.HTTP_201_CREATED)
async def create_external_import(
    file: UploadFile = File(...),
    subject_id: str | None = Form(default=None),
    duplicate_strategy: str = Form(default="skip"),
    db: Session = Depends(get_db),
) -> ImportRead:
    return await external_service.create_external_import(
        db,
        file,
        subject_id=subject_id or None,
        duplicate_strategy=duplicate_strategy,
    )


@router.get("/{import_id}", response_model=ImportRead)
def get_import(
    import_id: str,
    db: Session = Depends(get_db),
) -> ImportRead:
    return import_service.get_import_read(db, import_id)


@router.post("/{import_id}/confirm", response_model=ImportRead)
def confirm_import(
    import_id: str,
    payload: ImportConfirmRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ImportRead:
    try:
        result = import_service.confirm_import(db, import_id, payload)
    except DomainError:
        raise
    except Exception as exc:
        db.rollback()
        try:
            job = import_service.get_import(db, import_id)
            job.status = "failed"
            job.stage = "归档失败"
            job.error = "导入归档失败，资料已保留，请重试"
            job.finished_at = utc_now()
            db.commit()
        except Exception:
            db.rollback()
        raise DomainError(
            500,
            "import_confirm_failed",
            "导入归档失败，资料已保留，请重试",
        ) from exc
    if result.analysis_job_id and result.analysis_status == "running":
        background_tasks.add_task(
            import_service.run_import_analysis,
            import_id,
            result.analysis_job_id,
        )
    return result

@router.post("/{import_id}/retry", response_model=ImportRead)
def retry_import(
    import_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ImportRead:
    result = import_service.retry_import(db, import_id)
    if result.status == "queued":
        background_tasks.add_task(import_service.run_import, import_id)
    return result
