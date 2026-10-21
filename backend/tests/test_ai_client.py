from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.services.ai_client import AIClientError, OpenAICompatibleClient


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
            )
        return _chat_response('{"questions": []}')

    monkeypatch.setattr(client, "_request", fake_request)
    parsed = client.chat_json("system", "user")

    assert parsed == {"questions": []}
    assert "response_format" in bodies[0]
    assert "response_format" not in bodies[1]
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
