from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any, Protocol

import httpx

from app.core.config import Settings
from app.services.ai_config import config_source, effective_ai_settings

logger = logging.getLogger(__name__)


class AIClientError(Exception):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable
        self.status_code = status_code


class AIConfigurationError(AIClientError):
    pass


class AIClientCancelled(AIClientError):
    """Raised when the user asks to stop the current extraction."""

    def __init__(self) -> None:
        super().__init__("AI 任务已停止")


class AIClientProtocol(Protocol):
    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        cancel_check: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        ...


def ai_status(settings: Settings | None = None) -> dict[str, Any]:
    base = effective_ai_settings(settings)
    current = effective_ai_settings(base)
    configured = current.ai_configured
    if configured:
        message = "AI 已配置，可以测试连接或开始知识点提取"
    else:
        message = (
            "AI 未配置。请打开 /settings/ai 填写 API Base、API Key 和模型，"
            "或在 .env 中配置；密钥只保存在后端。"
        )
    return {
        "configured": configured,
        "provider": current.ai_provider,
        "model": current.ai_model,
        "api_base": current.ai_api_base,
        "key_configured": bool(
            current.ai_api_key
            and current.ai_api_key.get_secret_value().strip()
        ),
        "source": config_source(base),
        "message": message,
    }


class OpenAICompatibleClient:
    """Minimal OpenAI-compatible chat client with bounded retries."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or effective_ai_settings()
        if not self.settings.ai_configured:
            raise AIConfigurationError(
                "AI 未配置：请设置 AI_API_BASE、AI_API_KEY、AI_MODEL",
            )
        if self.settings.ai_provider not in {
            "openai",
            "openai-compatible",
            "custom",
        }:
            raise AIConfigurationError(
                f"不支持的 AI_PROVIDER：{self.settings.ai_provider}",
            )
        self.base_url = self.settings.ai_api_base.rstrip("/")
        self.model = self.settings.ai_model
        self.api_key = self.settings.ai_api_key.get_secret_value() if self.settings.ai_api_key else ""

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> httpx.Response:
        last_error: AIClientError | None = None
        attempts = self.settings.ai_max_retries + 1

        for attempt in range(attempts):
            if cancel_check is not None and cancel_check():
                raise AIClientCancelled()
            try:
                with httpx.Client(
                    timeout=self.settings.ai_timeout_seconds,
                ) as client:
                    response = client.request(
                        method,
                        url,
                        headers=self._headers(),
                        json=json_body,
                    )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = AIClientError(
                    "AI 请求超时或网络不可达",
                    retryable=True,
                )
                if attempt + 1 < attempts:
                    if cancel_check is not None and cancel_check():
                        raise AIClientCancelled() from exc
                    time.sleep(min(2**attempt, 8))
                    continue
                raise last_error from exc

            if cancel_check is not None and cancel_check():
                raise AIClientCancelled()

            if response.status_code < 400:
                return response

            status = response.status_code
            retryable = status == 429 or status >= 500
            message = _safe_provider_error(response)
            last_error = AIClientError(
                message,
                retryable=retryable,
                status_code=status,
            )
            if not retryable or attempt + 1 >= attempts:
                raise last_error

            delay = _retry_delay(response, attempt)
            logger.warning(
                "AI provider request failed with status=%s; retrying in %.1fs",
                status,
                delay,
            )
            if cancel_check is not None and cancel_check():
                raise AIClientCancelled()
            time.sleep(delay)

        raise last_error or AIClientError("AI 请求失败")

    def test_connection(self) -> str:
        response = self._request("GET", f"{self.base_url}/models")
        try:
            payload = response.json()
        except ValueError:
            return self.model
        models = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(models, list) and models:
            names = [
                item.get("id")
                for item in models
                if isinstance(item, dict) and item.get("id")
            ]
            if names and self.model not in names:
                return f"{self.model}（接口可用，但模型列表未包含该名称）"
        return self.model

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        cancel_check: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        response = self._request(
            "POST",
            f"{self.base_url}/chat/completions",
            json_body={
                "model": self.model,
                "temperature": self.settings.ai_temperature,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            cancel_check=cancel_check,
        )
        try:
            payload = response.json()
            choice = payload["choices"][0]
            content = choice["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AIClientError("AI 返回结构不符合 OpenAI 兼容格式") from exc

        if isinstance(content, list):
            content = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict)
            )
        if not isinstance(content, str) or not content.strip():
            raise AIClientError("AI 返回内容为空")

        text = content.strip()
        if text.startswith("```"):
            text = re_fenced_json(text)
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AIClientError("AI 返回内容不是有效 JSON") from exc
        if not isinstance(parsed, dict):
            raise AIClientError("AI 返回 JSON 顶层必须是对象")
        return parsed


def re_fenced_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


def _safe_provider_error(response: httpx.Response) -> str:
    status = response.status_code
    if status in {401, 403}:
        return "AI 认证失败，请检查 AI_API_KEY 是否有效"
    if status == 404:
        return "AI 接口不存在，请检查 AI_API_BASE 是否包含正确的 /v1 路径"
    if status == 429:
        return "AI 服务触发速率限制，请稍后重试或降低调用频率"
    if status >= 500:
        return f"AI 服务暂时不可用（HTTP {status}），可稍后重试"
    # Never echo provider error bodies: they can contain prompt or document
    # fragments. Auth, rate-limit, and server failures have explicit messages.
    return f"AI 请求失败（HTTP {status}），请检查模型名称、请求参数或服务状态"


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return min(max(float(retry_after), 0), 30)
        except ValueError:
            pass
    return min(2**attempt, 8)


def get_ai_client(settings: Settings | None = None) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(effective_ai_settings(settings))
