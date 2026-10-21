from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
# Source checkout: backend/app/core -> backend. Portable build: app/core -> dist root.
PORTABLE_ROOT = BACKEND_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or `.env`."""

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "BioLearn AI API"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./data/biolearn.db"
    upload_dir: Path = Path("./data/uploads")
    max_upload_bytes: int = Field(
        default=25 * 1024 * 1024,
        ge=1,
    )
    chunk_max_chars: int = Field(default=6000, ge=500)
    chunk_min_chars: int = Field(default=600, ge=0)
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]
    )
    # Capacitor ships the web build on https://localhost; LAN origins opt in.
    cors_extra_origins: list[str] = Field(default_factory=list)
    # Shared access token for LAN/external use. Empty keeps the historical
    # single-machine behaviour (loopback only). Health/docs stay anonymous.
    access_token: SecretStr | None = None
    # Explicit opt-in for listening on the LAN; the launcher keeps 127.0.0.1.
    allow_lan: bool = False

    ai_provider: str = "openai-compatible"
    ai_api_base: str = ""
    ai_api_key: SecretStr | None = None
    ai_model: str = ""
    ai_config_path: Path = Path("./data/ai_config.json")
    ai_timeout_seconds: float = Field(default=90.0, ge=1)
    ai_max_retries: int = Field(default=2, ge=0, le=10)
    ai_temperature: float = Field(default=0.2, ge=0, le=2)
    ai_max_points_per_chunk: int = Field(default=8, ge=1, le=30)
    ai_extraction_concurrency: int = Field(default=3, ge=1, le=8)
    ai_merge_batch_size: int = Field(default=40, ge=2, le=100)
    ai_outline_max_chars: int = Field(default=15000, ge=1000)
    serve_frontend: bool = True
    frontend_dist_dir: Path = PROJECT_ROOT / "frontend" / "dist"
    log_level: str = "info"
    log_dir: Path = Path("./data/logs")

    @property
    def auth_required(self) -> bool:
        return bool(
            self.access_token is not None
            and self.access_token.get_secret_value().strip()
        )

    @property
    def ai_configured(self) -> bool:
        return bool(
            self.ai_api_base.strip()
            and self.ai_model.strip()
            and self.ai_api_key is not None
            and self.ai_api_key.get_secret_value().strip()
        )

    def resolved(self, path: Path) -> Path:
        """Resolve a possibly relative path against the backend directory.

        Relative defaults such as ``./data/biolearn.db`` must keep working no
        matter which directory the launcher is started from.
        """

        expanded = path.expanduser()
        if expanded.is_absolute():
            return expanded
        return (BACKEND_DIR / expanded).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
