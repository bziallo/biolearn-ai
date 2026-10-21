from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.services.ai_client import (
    AIClientError,
    OpenAICompatibleClient,
    _json_mode_unsupported,
)


def _chat_response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}]},
    )


def test_chat_json_requests_json_mode_and_sends_it(
    app_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = OpenAICompatibleClient(app_settings)
    bodies: list[dict[str, Any]] = []

    def fake_request(method, url, *, json_body=None, cancel_check=None):
        bodies.append(json_body or {})
        return _chat_response('{"questions": []}')

    monkeypatch.setattr(client, "_request", fake_request)
    parsed = client.chat_json("system", "user")

    assert parsed == {"questions": []}
    assert bodies[0]["response_format"] == {"type": "json_object"}


def test_chat_json_degrades_when_provider_rejects_response_format(
    app_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = OpenAICompatibleClient(app_settings)
    bodies: list[dict[str, Any]] = []

    def fake_request(method, url, *, json_body=None, cancel_check=None):
        bodies.append(dict(json_body or {}))
        if len(bodies) == 1:
            raise AIClientError(
                "AI 请求被拒绝（HTTP 400）",
                status_code=400,
                kind="bad_request",
                json_mode_rejected=True,
            )
        return _chat_response('{"questions": []}')

    monkeypatch.setattr(client, "_request", fake_request)
    parsed = client.chat_json("system", "user")

    assert parsed == {"questions": []}
    assert "response_format" in bodies[0]
    assert "response_format" not in bodies[1]
    assert client.last_json_mode_fallback == {
        "status": 400,
        "reason": "response_format_not_supported",
    }
    # Once degraded, later calls do not pay for another 400.
    client.chat_json("system", "user")
    assert "response_format" not in bodies[2]


def test_chat_json_extracts_fenced_content(
    app_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = OpenAICompatibleClient(app_settings)

    def fake_request(method, url, *, json_body=None, cancel_check=None):
        return _chat_response(
            '以下是结果：\n```json\n{"questions": [{"stem": "题干"}]}\n```\n完成。'
        )

    monkeypatch.setattr(client, "_request", fake_request)
    assert client.chat_json("system", "user") == {
        "questions": [{"stem": "题干"}]
    }


def test_422_explicit_response_format_falls_back_once(
    app_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = OpenAICompatibleClient(app_settings)
    bodies: list[dict[str, Any]] = []

    def fake_request(method, url, *, json_body=None, cancel_check=None):
        bodies.append(dict(json_body or {}))
        if len(bodies) == 1:
            raise AIClientError(
                "AI 请求被拒绝（HTTP 422）",
                status_code=422,
                kind="bad_request",
                json_mode_rejected=True,
            )
        return _chat_response('{"questions": []}')

    monkeypatch.setattr(client, "_request", fake_request)
    assert client.chat_json("system", "user") == {"questions": []}
    assert "response_format" in bodies[0]
    assert "response_format" not in bodies[1]
    assert client.last_json_mode_fallback["status"] == 422


def test_422_other_parameter_error_does_not_degrade(
    app_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = OpenAICompatibleClient(app_settings)
    bodies: list[dict[str, Any]] = []

    def fake_request(method, url, *, json_body=None, cancel_check=None):
        bodies.append(dict(json_body or {}))
        raise AIClientError(
            "AI 请求被拒绝（HTTP 422）：消息格式不合法",
            status_code=422,
            kind="bad_request",
            json_mode_rejected=False,
        )

    monkeypatch.setattr(client, "_request", fake_request)
    with pytest.raises(AIClientError):
        client.chat_json("system", "user")
    assert len(bodies) == 1
    assert client.last_json_mode_fallback is None
    assert client._json_mode_enabled is True


def test_400_other_parameter_error_does_not_degrade(
    app_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = OpenAICompatibleClient(app_settings)
    bodies: list[dict[str, Any]] = []

    def fake_request(method, url, *, json_body=None, cancel_check=None):
        bodies.append(dict(json_body or {}))
        raise AIClientError(
            "AI 请求被拒绝（HTTP 400）：max_tokens 非法",
            status_code=400,
            kind="bad_request",
            json_mode_rejected=False,
        )

    monkeypatch.setattr(client, "_request", fake_request)
    with pytest.raises(AIClientError):
        client.chat_json("system", "user")
    assert len(bodies) == 1
    assert client._json_mode_enabled is True


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (422, {"error": {"message": "response_format is not supported"}}, True),
        (422, {"error": {"message": "unsupported parameter: response_format"}}, True),
        (422, {"error": {"message": "messages[0] is invalid"}}, False),
        (400, {"error": {"message": "max_tokens too large"}}, False),
        (400, {"error": {"message": "response_format json_object unsupported"}}, True),
        (500, {"error": {"message": "response_format unsupported"}}, False),
    ],
)
def test_json_mode_unsupported_detection_is_narrow(
    status: int,
    body: dict[str, Any],
    expected: bool,
) -> None:
    response = httpx.Response(status, json=body)
    assert _json_mode_unsupported(response) is expected


def test_chat_json_records_token_usage(
    app_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = OpenAICompatibleClient(app_settings)

    def fake_request(method, url, *, json_body=None, cancel_check=None):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"questions": []}'}}],
                "usage": {
                    "prompt_tokens": 123,
                    "completion_tokens": 45,
                    "total_tokens": 168,
                    "completion_tokens_details": {"reasoning_tokens": 20},
                },
            },
        )

    monkeypatch.setattr(client, "_request", fake_request)
    client.chat_json("system", "user")
    assert client.last_usage == {
        "prompt_tokens": 123,
        "completion_tokens": 45,
        "total_tokens": 168,
        "reasoning_tokens": 20,
    }
