import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.errors import domain_error_handler, validation_error_handler
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.security import AccessTokenMiddleware
from app.db.session import SessionLocal
from app.services.recovery import recover_interrupted_tasks


@asynccontextmanager
async def lifespan(_application: FastAPI):
    recover_interrupted_tasks()
    yield


def _mount_frontend(application: FastAPI, dist_dir: Path, api_prefix: str) -> None:
    """Serve the built SPA from FastAPI so one process runs the whole app."""

    index_file = dist_dir / "index.html"
    if not index_file.is_file():
        return

    reserved_prefixes = {
        segment
        for segment in (
            api_prefix.strip("/").split("/")[0],
            "api",
            "health",
            "docs",
            "redoc",
            "openapi.json",
        )
        if segment
    }
    assets_dir = dist_dir / "assets"
    if assets_dir.is_dir():
        application.mount(
            "/assets",
            StaticFiles(directory=assets_dir),
            name="assets",
        )

    @application.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        first_segment = full_path.split("/")[0]
        if full_path.startswith(api_prefix.strip("/")):
            raise DomainError(404, "not_found", "接口不存在")
        if first_segment in reserved_prefixes:
            raise DomainError(404, "not_found", "资源不存在")
        candidate = (dist_dir / full_path).resolve()
        if (
            full_path
            and dist_dir in candidate.parents
            and candidate.is_file()
        ):
            return FileResponse(candidate)
        return FileResponse(index_file)


def _origin_pattern(settings) -> str:
    """Allow loopback, the Capacitor shell and explicitly listed LAN origins."""

    parts = [
        r"http://(localhost|127\.0\.0\.1)(:\d+)?",
        r"https://localhost(:\d+)?",
        r"capacitor://localhost",
    ]
    for origin in settings.cors_origins + settings.cors_extra_origins:
        escaped = re.escape(origin.strip().rstrip("/"))
        pattern = f"{escaped}(:\\d+)?"
        if pattern not in parts:
            parts.append(pattern)
    return "|".join(f"(?:{part})" for part in parts)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=__version__,
        debug=settings.debug,
        lifespan=lifespan,
    )
    application.state.session_factory = SessionLocal
    application.add_middleware(AccessTokenMiddleware)
    # Add CORS last so authentication/authorization error responses also carry
    # CORS headers for the browser and Android WebView clients.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=_origin_pattern(settings),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_exception_handler(DomainError, domain_error_handler)
    application.add_exception_handler(
        RequestValidationError,
        validation_error_handler,
    )
    application.include_router(api_router, prefix=settings.api_v1_prefix)
    if settings.serve_frontend:
        _mount_frontend(
            application,
            settings.resolved(settings.frontend_dist_dir),
            settings.api_v1_prefix,
        )
    return application


app = create_app()
