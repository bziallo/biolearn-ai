from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr

from app.core.config import Settings, get_settings

ALLOWED_AI_PROVIDERS = {"openai", "openai-compatible", "custom"}


class AIRuntimeConfig(BaseModel):
    provider: str = "openai-compatible"
    api_base: str = ""
    api_key: str = ""
    model: str = ""
    timeout_seconds: float | None = Field(default=None, ge=1)
    max_retries: int | None = Field(default=None, ge=0, le=10)
    temperature: float | None = Field(default=None, ge=0, le=2)


def config_path(settings: Settings | None = None) -> Path:
    current = settings or get_settings()
    return current.resolved(Path(current.ai_config_path))


def load_runtime_config(
    settings: Settings | None = None,
) -> AIRuntimeConfig | None:
    path = config_path(settings)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return AIRuntimeConfig.model_validate(payload)
    except (OSError, ValueError):
        # A corrupt local config should be treated as unconfigured, not crash
        # the application. The key is never logged here.
        return None


def save_runtime_config(
    runtime: AIRuntimeConfig,
    settings: Settings | None = None,
) -> None:
    path = config_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(runtime.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def clear_runtime_config(settings: Settings | None = None) -> None:
    config_path(settings).unlink(missing_ok=True)


def effective_ai_settings(settings: Settings | None = None) -> Settings:
    base = settings or get_settings()
    runtime = load_runtime_config(base)
    if runtime is None:
        return base

    updates: dict[str, object] = {}
    if runtime.provider.strip():
        updates["ai_provider"] = runtime.provider.strip()
    if runtime.api_base.strip():
        updates["ai_api_base"] = runtime.api_base.strip()
    if runtime.model.strip():
        updates["ai_model"] = runtime.model.strip()
    if runtime.api_key.strip():
        updates["ai_api_key"] = SecretStr(runtime.api_key.strip())
    if runtime.timeout_seconds is not None:
        updates["ai_timeout_seconds"] = runtime.timeout_seconds
    if runtime.max_retries is not None:
        updates["ai_max_retries"] = runtime.max_retries
    if runtime.temperature is not None:
        updates["ai_temperature"] = runtime.temperature
    return base.model_copy(update=updates)


def config_source(settings: Settings | None = None) -> str:
    base = settings or get_settings()
    runtime = load_runtime_config(base)
    if runtime is not None and any(
        value
        for value in (
            runtime.api_base,
            runtime.api_key,
            runtime.model,
        )
    ):
        return "runtime"
    return "environment" if base.ai_configured else "unconfigured"
