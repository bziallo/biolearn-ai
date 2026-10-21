from fastapi import APIRouter

from app.api.v1 import (
    admin,
    ai,
    auth,
    chapters,
    documents,
    health,
    imports,
    knowledge,
    practice,
    questions,
    subjects,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(ai.router)
api_router.include_router(imports.router)
api_router.include_router(subjects.router)
api_router.include_router(chapters.router)
api_router.include_router(documents.router)
api_router.include_router(knowledge.points_router)
api_router.include_router(knowledge.jobs_router)
api_router.include_router(questions.router)
api_router.include_router(practice.router)
