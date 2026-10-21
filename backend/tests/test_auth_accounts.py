from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.models import Question
from app.services import auth as auth_service

PASSWORD = "CorrectHorseBattery2"


def _login(client: TestClient, username: str, password: str = PASSWORD):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    return response


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _owner(client: TestClient, session_factory) -> tuple[str, str]:
    with session_factory() as db:
        owner = auth_service.create_owner(
            db,
            username="owner",
            password=PASSWORD,
            display_name="Owner",
        )
        owner_id = owner.id
    response = _login(client, "owner")
    assert response.status_code == 200, response.text
    return response.json()["token"], owner_id


def _create_subject(client: TestClient, headers: dict[str, str], name: str) -> str:
    response = client.post(
        "/api/v1/subjects",
        headers=headers,
        json={"name": name, "description": ""},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_question(
    session_factory,
    *,
    subject_id: str,
    chapter_id: str,
    stem: str,
) -> None:
    from app.models import Chapter, Document, KnowledgePoint

    with session_factory() as db:
        document = Document(
            subject_id=subject_id,
            chapter_id=chapter_id,
            name="auth test document",
            original_filename="auth.txt",
            storage_name="auth.txt",
            mime_type="text/plain",
            extension=".txt",
            size_bytes=10,
            sha256="a" * 64,
            status="parsed",
            page_count=1,
        )
        db.add(document)
        db.flush()
        point = KnowledgePoint(
            subject_id=subject_id,
            chapter_id=chapter_id,
            document_id=document.id,
            name="授权测试知识点",
            explanation="用于权限测试的合成知识点。",
            core_points=["权限"],
            source_quote="合成内容",
            source_quote_verified=True,
            source_page=1,
            review_status="approved",
            needs_review=False,
            origin="manual",
        )
        db.add(point)
        db.flush()
        question = Question(
            subject_id=subject_id,
            chapter_id=chapter_id,
            type="single_choice",
            stem=stem,
            options=[
                {"key": "A", "text": "正确选项"},
                {"key": "B", "text": "错误选项"},
            ],
            answer={"choices": ["A"]},
            grading_rule={"mode": "choice_exact", "case_sensitive": False},
            explanation="这是用于权限测试的解析。",
            difficulty="easy",
            status="approved",
            origin="manual",
            score=1.0,
        )
        question.knowledge_points = [point]
        db.add(question)
        db.commit()


def test_owner_login_and_anonymous_are_separated(
    client: TestClient,
    session_factory,
) -> None:
    auth_service.reset_login_attempts()
    owner_token, owner_id = _owner(client, session_factory)

    anonymous = client.get("/api/v1/subjects")
    assert anonymous.status_code == 401
    assert anonymous.json()["detail"]["code"] == "auth_required"

    bad = _login(client, "owner", "wrong-password")
    assert bad.status_code == 401

    subjects = client.get("/api/v1/subjects", headers=_headers(owner_token))
    assert subjects.status_code == 200

    with session_factory() as db:
        owner = db.get(__import__("app.models", fromlist=["User"]).User, owner_id)
        assert owner is not None
        assert owner.password_hash != PASSWORD
        assert owner.password_hash.startswith("$argon2")


def test_invited_user_read_only_practice_and_owner_cannot_read_it(
    client: TestClient,
    session_factory,
) -> None:
    auth_service.reset_login_attempts()
    owner_token, owner_id = _owner(client, session_factory)
    owner_headers = _headers(owner_token)

    subject_id = _create_subject(client, owner_headers, "Owner 私有学科")
    chapter = client.post(
        f"/api/v1/subjects/{subject_id}/chapters",
        headers=owner_headers,
        json={"name": "章节一"},
    )
    assert chapter.status_code == 201, chapter.text
    chapter_id = chapter.json()["id"]
    _create_question(
        session_factory,
        subject_id=subject_id,
        chapter_id=chapter_id,
        stem="授权测试单选题？",
    )

    invite = client.post(
        "/api/v1/admin/invitations",
        headers=owner_headers,
        json={"note": "friend"},
    )
    assert invite.status_code == 200, invite.text
    invite_token = invite.json()["invitation_token"]
    assert invite_token

    accepted = client.post(
        "/api/v1/auth/invitations/accept",
        json={
            "token": invite_token,
            "username": "friend",
            "password": PASSWORD,
            "display_name": "Friend",
        },
    )
    assert accepted.status_code == 200, accepted.text
    friend_headers = _headers(accepted.json()["token"])
    friend_id = accepted.json()["user"]["id"]

    # Before a grant: no subjects visible.
    assert client.get("/api/v1/subjects", headers=friend_headers).json() == []

    grant = client.post(
        "/api/v1/admin/grants",
        headers=owner_headers,
        json={
            "subject_id": subject_id,
            "grantee_user_id": friend_id,
            "permission": "read",
        },
    )
    assert grant.status_code == 200, grant.text

    visible = client.get("/api/v1/subjects", headers=friend_headers)
    assert visible.status_code == 200
    assert [item["id"] for item in visible.json()] == [subject_id]

    # Invited users cannot write or reach owner-only endpoints.
    assert (
        client.post(
            "/api/v1/subjects",
            headers=friend_headers,
            json={"name": "不该创建"},
        ).status_code
        == 403
    )
    assert client.get("/api/v1/ai/status", headers=friend_headers).status_code == 403
    assert client.get("/api/v1/imports", headers=friend_headers).status_code == 403

    practice = client.post(
        "/api/v1/practice/sessions",
        headers=friend_headers,
        json={"subject_id": subject_id, "count": 1},
    )
    assert practice.status_code == 200, practice.text
    session_id = practice.json()["id"]
    question = practice.json()["questions"][0]
    assert question["id"]

    # Owner must not read a friend's practice record.
    assert (
        client.get(
            f"/api/v1/practice/sessions/{session_id}", headers=owner_headers
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/practice/sessions/{session_id}/result",
            headers=owner_headers,
        ).status_code
        == 404
    )

    submit = client.post(
        f"/api/v1/practice/sessions/{session_id}/submit",
        headers=friend_headers,
        json={
            "answers": [
                {"question_id": question["id"], "user_answer": {"choices": ["A"]}}
            ]
        },
    )
    assert submit.status_code == 200, submit.text
    assert submit.json()["session"]["score"] == 100

    # Owner cannot see it in the list either.
    owner_sessions = client.get(
        "/api/v1/practice/sessions", headers=owner_headers
    )
    assert owner_sessions.status_code == 200
    assert session_id not in [item["id"] for item in owner_sessions.json()]


def test_second_user_cannot_read_first_users_subject(
    client: TestClient,
    session_factory,
) -> None:
    auth_service.reset_login_attempts()
    owner_token, _ = _owner(client, session_factory)
    owner_headers = _headers(owner_token)
    first_subject = _create_subject(client, owner_headers, "A 的学科")
    second_subject = _create_subject(client, owner_headers, "B 的学科")

    def make_user(username: str) -> dict[str, str]:
        invite = client.post(
            "/api/v1/admin/invitations", headers=owner_headers, json={}
        )
        accepted = client.post(
            "/api/v1/auth/invitations/accept",
            json={
                "token": invite.json()["invitation_token"],
                "username": username,
                "password": PASSWORD,
            },
        )
        assert accepted.status_code == 200, accepted.text
        user_id = accepted.json()["user"]["id"]
        return _headers(accepted.json()["token"]), user_id

    a_headers, a_id = make_user("alice")
    b_headers, b_id = make_user("bob")
    for subject_id, user_id in ((first_subject, a_id), (second_subject, b_id)):
        grant = client.post(
            "/api/v1/admin/grants",
            headers=owner_headers,
            json={
                "subject_id": subject_id,
                "grantee_user_id": user_id,
                "permission": "read",
            },
        )
        assert grant.status_code == 200

    assert [item["id"] for item in client.get("/api/v1/subjects", headers=a_headers).json()] == [
        first_subject
    ]
    assert [item["id"] for item in client.get("/api/v1/subjects", headers=b_headers).json()] == [
        second_subject
    ]
    assert (
        client.get(f"/api/v1/subjects/{second_subject}", headers=a_headers).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/subjects/{first_subject}", headers=b_headers).status_code
        == 404
    )


def test_invitation_single_use_and_session_revocation(
    client: TestClient,
    session_factory,
) -> None:
    auth_service.reset_login_attempts()
    owner_token, _ = _owner(client, session_factory)
    owner_headers = _headers(owner_token)
    invite = client.post(
        "/api/v1/admin/invitations", headers=owner_headers, json={}
    )
    assert invite.status_code == 200, invite.text
    token = invite.json()["invitation_token"]

    first = client.post(
        "/api/v1/auth/invitations/accept",
        json={"token": token, "username": "once", "password": PASSWORD},
    )
    assert first.status_code == 200, first.text
    reused = client.post(
        "/api/v1/auth/invitations/accept",
        json={"token": token, "username": "twice", "password": PASSWORD},
    )
    assert reused.status_code == 422

    user_headers = _headers(first.json()["token"])
    assert client.get("/api/v1/subjects", headers=user_headers).status_code == 200
    logout = client.post("/api/v1/auth/logout", headers=user_headers)
    assert logout.status_code == 200
    assert client.get("/api/v1/subjects", headers=user_headers).status_code == 401


def test_disabled_user_cannot_login_and_owner_only_admin(
    client: TestClient,
    session_factory,
) -> None:
    auth_service.reset_login_attempts()
    owner_token, _ = _owner(client, session_factory)
    owner_headers = _headers(owner_token)
    invite = client.post(
        "/api/v1/admin/invitations", headers=owner_headers, json={}
    )
    assert invite.status_code == 200, invite.text
    accepted = client.post(
        "/api/v1/auth/invitations/accept",
        json={
            "token": invite.json()["invitation_token"],
            "username": "disabled-user",
            "password": PASSWORD,
        },
    )
    user_id = accepted.json()["user"]["id"]
    user_headers = _headers(accepted.json()["token"])

    assert client.get("/api/v1/admin/users", headers=user_headers).status_code == 403
    disable = client.patch(
        f"/api/v1/admin/users/{user_id}",
        headers=owner_headers,
        json={"status": "disabled"},
    )
    assert disable.status_code == 200, disable.text
    assert _login(client, "disabled-user").status_code == 403
    assert client.get("/api/v1/subjects", headers=user_headers).status_code == 401


def test_revoking_a_grant_takes_effect_immediately(
    client: TestClient,
    session_factory,
) -> None:
    auth_service.reset_login_attempts()
    owner_token, _ = _owner(client, session_factory)
    owner_headers = _headers(owner_token)
    subject_id = _create_subject(client, owner_headers, "临时共享学科")
    invite = client.post(
        "/api/v1/admin/invitations", headers=owner_headers, json={}
    )
    accepted = client.post(
        "/api/v1/auth/invitations/accept",
        json={
            "token": invite.json()["invitation_token"],
            "username": "revoked-user",
            "password": PASSWORD,
        },
    )
    friend_headers = _headers(accepted.json()["token"])
    friend_id = accepted.json()["user"]["id"]

    granted = client.post(
        "/api/v1/admin/grants",
        headers=owner_headers,
        json={
            "subject_id": subject_id,
            "grantee_user_id": friend_id,
            "permission": "read",
        },
    )
    assert granted.status_code == 200, granted.text
    assert len(client.get("/api/v1/subjects", headers=friend_headers).json()) == 1

    revoked = client.delete(
        f"/api/v1/admin/grants/{granted.json()['id']}", headers=owner_headers
    )
    assert revoked.status_code == 204
    assert client.get("/api/v1/subjects", headers=friend_headers).json() == []
    assert (
        client.get(f"/api/v1/subjects/{subject_id}", headers=friend_headers).status_code
        == 404
    )
