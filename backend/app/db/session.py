from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import BACKEND_DIR, PORTABLE_ROOT, get_settings

settings = get_settings()
# Source checkout: backend/. Portable build: the distribution root (app/, data/, python/).
DATA_ROOT = PORTABLE_ROOT if PORTABLE_ROOT != BACKEND_DIR.parent else BACKEND_DIR
if DATA_ROOT != BACKEND_DIR and not (BACKEND_DIR / "data").exists():
    BACKEND_DIR = DATA_ROOT


def resolve_sqlite_path(database_url: str) -> Path | None:
    """Return the absolute file path of a SQLite URL, if it has one."""

    normalized = normalize_database_url(database_url)
    prefix = "sqlite:///"
    if not normalized.startswith(prefix) or ":memory:" in normalized:
        return None
    return Path(normalized[len(prefix) :]).expanduser()


def _ensure_sqlite_parent(database_url: str) -> None:
    database_path = resolve_sqlite_path(database_url)
    if database_path is None:
        return
    database_path.parent.mkdir(parents=True, exist_ok=True)


def normalize_database_url(database_url: str) -> str:
    """Make relative SQLite paths independent of the working directory."""

    prefix = "sqlite:///"
    if not database_url.startswith(prefix) or ":memory:" in database_url:
        return database_url
    raw_path = database_url[len(prefix) :]
    if not raw_path or raw_path.startswith("/") or Path(raw_path).is_absolute():
        return database_url
    return f"{prefix}{(BACKEND_DIR / raw_path).as_posix()}"


def build_engine(database_url: str) -> Engine:
    """Build an engine with SQLite foreign-key enforcement enabled."""

    database_url = normalize_database_url(database_url)
    _ensure_sqlite_parent(database_url)
    engine = create_engine(
        database_url,
        connect_args={
            "check_same_thread": False,
        }
        if database_url.startswith("sqlite")
        else {},
    )

    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(
            dbapi_connection: object,
            _connection_record: object,
        ) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = build_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield one database session per request."""

    with SessionLocal() as session:
        yield session
