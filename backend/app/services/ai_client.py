from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from typing import Any, Protocol

import httpx

from app.core.config import Settings
from app.services.ai_config import config_source, effective_ai_settings

logger = logging.getLogger(__name__)


class AIClientError(Exception):
    """Provider/transport/parse failure with a machine-readable category.

    ``kind`` is one of: configuration, timeout, network, auth, quota,
    rate_limit, server, bad_request, invalid_json, bad_shape, cancelled.
    Callers surface the message and can store ``kind`` in job timings without
    exposing prompts or credentials.
    """

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
        kind: str = "unknown",
        error_code: str | None = None,
        json_mode_rejected: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable
        self.status_code = status_code
        self.kind = kind
        self.error_code = error_code
        # True only when the provider body explicitly names response_format /
        # json_object as unsupported. Never inferred from status alone.
        self.json_mode_rejected = json_mode_rejected


class AIConfigurationError(AIClientError):
    def __init__(self, message: str) -> None:
        super().__init__(message, kind="configuration")


class AIClientCancelled(AIClientError):
    """Raised when the user asks to stop the current extraction."""

    def __init__(self) -> None:
        super().__init__("AI 任务已停止", kind="cancelled")


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
        # Flipped off for the rest of this client's life if the provider
        # rejects response_format; avoids paying for the same error every call.
        self._json_mode_enabled = bool(self.settings.ai_json_mode)
        # Populated by chat_json; used by metrics/evaluation and job timings.
        self.last_usage: dict[str, int] = {}
        self.last_json_mode_fallback: dict[str, Any] | None = None

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
            except httpx.TimeoutException as exc:
                last_error = AIClientError(
                    f"AI 请求超时（超过 {self.settings.ai_timeout_seconds:g} 秒），"
                    "请稍后重试或减少一次生成的知识点/题目数量",
                    retryable=True,
                    kind="timeout",
                )
                if attempt + 1 < attempts:
                    if cancel_check is not None and cancel_check():
                        raise AIClientCancelled() from exc
                    time.sleep(min(2**attempt, 8))
                    continue
                raise last_error from exc
            except httpx.TransportError as exc:
                last_error = AIClientError(
                    "无法连接 AI 服务（网络错误），请检查网络、代理或 AI_API_BASE 地址",
                    retryable=True,
                    kind="network",
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
                kind=_error_kind(status),
                error_code=_provider_error_code(response),
                json_mode_rejected=_json_mode_unsupported(response),
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
        self.last_usage = {}
        self.last_json_mode_fallback = None
        body: dict[str, Any] = {
            "model": self.model,
            "temperature": self.settings.ai_temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        used_json_mode = self._json_mode_enabled
        if used_json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            response = self._request(
                "POST",
                f"{self.base_url}/chat/completions",
                json_body=body,
                cancel_check=cancel_check,
            )
        except AIClientError as exc:
            # Only fall back when the provider explicitly blames
            # response_format (400 or 422). Other parameter errors must surface.
            if used_json_mode and exc.json_mode_rejected:
                logger.info(
                    "AI provider rejected response_format (HTTP %s); retrying without JSON mode",
                    exc.status_code,
                )
                self._json_mode_enabled = False
                self.last_json_mode_fallback = {
                    "status": exc.status_code,
                    "reason": "response_format_not_supported",
                }
                body.pop("response_format", None)
                response = self._request(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json_body=body,
                    cancel_check=cancel_check,
                )
            else:
                raise

        try:
            payload = response.json()
            choice = payload["choices"][0]
            content = choice["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise AIClientError(
                "AI 返回结构不符合 OpenAI 兼容格式（缺少 choices/message/content）",
                kind="bad_shape",
            ) from exc

        usage = payload.get("usage")
        if isinstance(usage, dict):
            details = usage.get("completion_tokens_details")
            reasoning = (
                details.get("reasoning_tokens")
                if isinstance(details, dict)
                else None
            )
            self.last_usage = {
                "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                "completion_tokens": int(usage.get("completion_tokens") or 0),
                "total_tokens": int(usage.get("total_tokens") or 0),
                "reasoning_tokens": int(reasoning or 0),
            }

        if isinstance(content, list):
            content = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict)
            )
        if not isinstance(content, str) or not content.strip():
            raise AIClientError(
                "AI 返回内容为空（可能是内容过滤或模型提前停止）",
                kind="bad_shape",
            )

        try:
            parsed = extract_json_object(content)
        except ValueError as exc:
            raise AIClientError(
                "AI 返回内容不是有效 JSON（已尝试提取代码块/前后文本）",
                kind="invalid_json",
                error_code="invalid_json",
            ) from exc
        if not isinstance(parsed, dict):
            raise AIClientError(
                "AI 返回 JSON 顶层必须是对象",
                kind="bad_shape",
            )
        return parsed


_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract one JSON object from model text without guessing fields.

    Handles plain JSON, ```json fences, and prose before/after the object.
    Raises ValueError when no complete object can be decoded, so callers never
    turn unparseable output into a fake success.
    """

    if not isinstance(text, str) or not text.strip():
        raise ValueError("empty content")

    candidates: list[str] = []
    stripped = text.strip()
    candidates.append(stripped)
    for match in _FENCE_RE.finditer(text):
        block = match.group(1).strip()
        if block:
            candidates.append(block)
    if stripped.startswith("```"):
        candidates.append(re_fenced_json(stripped))

    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            value = None
        if isinstance(value, dict):
            return value
        # Prose or trailing explanations: scan for the first decodable object.
        for index, char in enumerate(candidate):
            if char != "{":
                continue
            try:
                value, _ = decoder.raw_decode(candidate, index)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
    raise ValueError("no json object found")


def re_fenced_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


def _json_mode_unsupported(response: httpx.Response) -> bool:
    """Return True only when the body explicitly blames response_format.

    Kept deliberately narrow: a 400/422 caused by another parameter must not
    silently disable JSON mode. The body is inspected in memory and never
    logged or stored.
    """

    if response.status_code not in {400, 422}:
        return False
    try:
        body = response.text[:4000].lower()
    except Exception:  # pragma: no cover - defensive
        return False
    markers = (
        "response_format",
        "response format",
        "json_object",
        "json mode",
        "json mode is not supported",
        "unsupported parameter",
    )
    return any(marker in body for marker in markers)


def _provider_error_code(response: httpx.Response) -> str | None:
    """Read only the provider's error code/type, never its message body."""

    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if isinstance(error, dict):
        code = error.get("code") or error.get("type")
        if isinstance(code, str) and len(code) <= 80:
            return code
    code = payload.get("code")
    return code if isinstance(code, str) and len(code) <= 80 else None


def _error_kind(status: int) -> str:
    if status in {401, 403}:
        return "auth"
    if status == 402:
        return "quota"
    if status == 404:
        return "bad_request"
    if status == 429:
        return "rate_limit"
    if status >= 500:
        return "server"
    return "bad_request"


def _safe_provider_error(response: httpx.Response) -> str:
    status = response.status_code
    code = _provider_error_code(response) or ""
    lowered = code.lower()
    if status in {401, 403} or "invalid_api_key" in lowered:
        return "AI 认证失败，请检查 AI_API_KEY 是否有效"
    if status == 402 or "insufficient" in lowered or "quota" in lowered:
        return "AI 账户余额不足或额度已用尽（HTTP 402），请充值或更换 Key 后重试"
    if status == 404:
        return "AI 接口或模型不存在，请检查 AI_API_BASE 是否包含 /v1，以及模型名称是否正确"
    if status == 429 or "rate_limit" in lowered:
        return "AI 服务触发速率限制（HTTP 429），请稍后重试或降低调用频率"
    if status >= 500:
        return f"AI 服务暂时不可用（HTTP {status}），可稍后重试"
    if "context_length" in lowered or "too long" in lowered:
        return "AI 上下文超过模型上限，请减少一次生成的知识点或题目数量"
    if "content_filter" in lowered:
        return "AI 内容被安全策略拦截，请调整知识点表述后重试"
    # Never echo provider messages: they can contain prompt or document
    # fragments. Auth, quota, rate-limit, and server failures have explicit
    # messages above.
    return f"AI 请求被拒绝（HTTP {status}），请检查模型名称、请求参数或服务状态"


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
