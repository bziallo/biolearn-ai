from fastapi.testclient import TestClient


def create_subject(
    client: TestClient,
    *,
    name: str = "生物化学",
    description: str = "从分子层面理解生命过程。",
    color: str | None = "#2dd4bf",
    icon: str | None = "🧬",
    sort_order: int | None = None,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/subjects",
        json={
            "name": name,
            "description": description,
            "color": color,
            "icon": icon,
            "sort_order": sort_order,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_subject_crud_counts_and_cascade_confirmation(
    client: TestClient,
) -> None:
    subject = create_subject(client)
    subject_id = subject["id"]

    assert subject["name"] == "生物化学"
    assert subject["chapter_count"] == 0
    assert subject["sort_order"] == 0

    response = client.get("/api/v1/subjects")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [subject_id]

    response = client.get(f"/api/v1/subjects/{subject_id}")
    assert response.status_code == 200
    assert response.json()["description"] == "从分子层面理解生命过程。"

    response = client.patch(
        f"/api/v1/subjects/{subject_id}",
        json={
            "name": "生物化学（更新）",
            "description": "更新后的简介。",
            "color": "#22c55e",
            "icon": "🧪",
        },
    )
    assert response.status_code == 200
    assert response.json()["name"] == "生物化学（更新）"
    assert response.json()["color"] == "#22c55e"

    chapter_response = client.post(
        f"/api/v1/subjects/{subject_id}/chapters",
        json={"name": "蛋白质结构"},
    )
    assert chapter_response.status_code == 201

    response = client.get(f"/api/v1/subjects/{subject_id}")
    assert response.json()["chapter_count"] == 1

    response = client.delete(f"/api/v1/subjects/{subject_id}")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "subject_has_chapters"
    assert response.json()["detail"]["chapter_count"] == 1

    assert client.get(f"/api/v1/subjects/{subject_id}").status_code == 200

    response = client.delete(
        f"/api/v1/subjects/{subject_id}",
        params={"cascade": "true"},
    )
    assert response.status_code == 204
    assert client.get(f"/api/v1/subjects/{subject_id}").status_code == 404
    assert client.get("/api/v1/subjects").json() == []


def test_subject_delete_without_chapters(client: TestClient) -> None:
    subject = create_subject(client, name="生理学")

    response = client.delete(f"/api/v1/subjects/{subject['id']}")

    assert response.status_code == 204
    assert client.get("/api/v1/subjects").json() == []


def test_subject_validation_and_not_found(client: TestClient) -> None:
    response = client.post("/api/v1/subjects", json={"name": "   "})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "validation_error"

    response = client.post(
        "/api/v1/subjects",
        json={"name": "细胞生物学", "color": "green"},
    )
    assert response.status_code == 422

    response = client.get("/api/v1/subjects/does-not-exist")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "subject_not_found"

    response = client.patch(
        "/api/v1/subjects/does-not-exist",
        json={"name": "不存在"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "subject_not_found"

    response = client.delete("/api/v1/subjects/does-not-exist")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "subject_not_found"


def test_subject_null_required_field_is_rejected(
    client: TestClient,
) -> None:
    subject = create_subject(client)

    response = client.patch(
        f"/api/v1/subjects/{subject['id']}",
        json={"name": None},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "validation_error"


def test_subject_sort_order_auto_increments(client: TestClient) -> None:
    first = create_subject(client, name="微生物学")
    second = create_subject(client, name="免疫学")
    explicit = create_subject(client, name="药理学", sort_order=500)

    assert first["sort_order"] == 0
    assert second["sort_order"] == 10
    assert explicit["sort_order"] == 500
