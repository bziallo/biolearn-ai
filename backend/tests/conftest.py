from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.main as app_main
import app.models  # noqa: F401
from app.core.config import Settings
from app.db.base import Base
from app.db.session import build_engine, get_db
from app.main import app


@pytest.fixture
def db_engine(tmp_path: Path) -> Generator[Engine, None, None]:
    engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def session_factory(db_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(
        bind=db_engine,
        autoflush=False,
        expire_on_commit=False,
    )


@pytest.fixture
def app_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        upload_dir=tmp_path / "uploads",
        ai_config_path=tmp_path / "ai_config.json",
        max_upload_bytes=1024 * 1024,
        chunk_max_chars=500,
        chunk_min_chars=20,
        ai_api_base="http://ai.test/v1",
        ai_api_key=SecretStr("test-key"),
        ai_model="test-model",
        ai_timeout_seconds=1,
        ai_max_retries=0,
        ai_merge_batch_size=10,
    )


@pytest.fixture
def client(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    # The lifespan hook normally marks interrupted real tasks as failed. Tests
    # must never touch the real database, so neutralize that startup recovery
    # here; recovery itself is covered directly in test_knowledge.py.
    monkeypatch.setattr(app_main, "recover_interrupted_tasks", lambda: None)

    def override_get_db() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
