from fastapi import APIRouter

from app.core.errors import DomainError
from app.schemas.ai import (
    AIConnectionTestResponse,
    AIProviderConfigRequest,
    AIStatusResponse,
)
from app.services.ai_client import (
    AIClientError,
    ai_status,
    get_ai_client,
)
from app.services.ai_config import (
    ALLOWED_AI_PROVIDERS,
    AIRuntimeConfig,
    clear_runtime_config,
    load_runtime_config,
    save_runtime_config,
)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status", response_model=AIStatusResponse)
def get_ai_status() -> AIStatusResponse:
    return AIStatusResponse(**ai_status())


@router.get("/config", response_model=AIStatusResponse)
def get_ai_config() -> AIStatusResponse:
    return AIStatusResponse(**ai_status())


@router.put("/config", response_model=AIStatusResponse)
def update_ai_config(payload: AIProviderConfigRequest) -> AIStatusResponse:
    if payload.provider not in ALLOWED_AI_PROVIDERS:
        raise DomainError(
            422,
            "unsupported_ai_provider",
            "不支持的 AI_PROVIDER",
        )

    existing = load_runtime_config() or AIRuntimeConfig()
    api_key = existing.api_key
    if payload.clear_key:
        api_key = ""
    elif payload.api_key is not None:
        candidate = payload.api_key.get_secret_value().strip()
        if candidate:
            api_key = candidate

    runtime = AIRuntimeConfig(
        provider=payload.provider,
        api_base=(
            payload.api_base.strip()
            if payload.api_base is not None
            else existing.api_base
        ),
        model=(
            payload.model.strip()
            if payload.model is not None
            else existing.model
        ),
        api_key=api_key,
        timeout_seconds=(
            payload.timeout_seconds
            if payload.timeout_seconds is not None
            else existing.timeout_seconds
        ),
        max_retries=(
            payload.max_retries
            if payload.max_retries is not None
            else existing.max_retries
        ),
        temperature=(
            payload.temperature
            if payload.temperature is not None
            else existing.temperature
        ),
    )
    save_runtime_config(runtime)
    return AIStatusResponse(**ai_status())


@router.delete("/config", response_model=AIStatusResponse)
def delete_ai_config() -> AIStatusResponse:
    clear_runtime_config()
    return AIStatusResponse(**ai_status())


@router.post("/test", response_model=AIConnectionTestResponse)
def test_ai_connection() -> AIConnectionTestResponse:
    try:
        client = get_ai_client()
        model = client.test_connection()
        return AIConnectionTestResponse(
            ok=True,
            message="AI 连接成功",
            model=model,
        )
    except AIClientError as exc:
        raise DomainError(
            502,
            "ai_connection_failed",
            exc.message,
        ) from exc
