from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.session import build_engine
from app.models import Chapter, Subject


def create_subject(client: TestClient, name: str = "细胞生物学") -> dict:
    response = client.post(
        "/api/v1/subjects",
        json={"name": name, "icon": "🧫", "color": "#a78bfa"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_chapter(
    client: TestClient,
    subject_id: str,
    name: str,
    *,
    parent_id: str | None = None,
) -> dict:
    response = client.post(
        f"/api/v1/subjects/{subject_id}/chapters",
        json={"name": name, "description": f"{name}简介", "parent_id": parent_id},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_chapter_crud_three_level_tree_and_detail(
    client: TestClient,
) -> None:
    subject = create_subject(client)
    root = create_chapter(client, subject["id"], "细胞膜")
    child = create_chapter(
        client,
        subject["id"],
        "膜运输",
        parent_id=root["id"],
    )
    grandchild = create_chapter(
        client,
        subject["id"],
        "主动运输",
        parent_id=child["id"],
    )

    response = client.get(f"/api/v1/subjects/{subject['id']}/chapters")
    assert response.status_code == 200
    tree = response.json()
    assert len(tree) == 1
    assert tree[0]["name"] == "细胞膜"
    assert tree[0]["children"][0]["name"] == "膜运输"
    assert tree[0]["children"][0]["children"][0]["name"] == "主动运输"

    response = client.get(f"/api/v1/chapters/{grandchild['id']}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["subject"]["id"] == subject["id"]
    assert detail["parent"]["name"] == "膜运输"
    assert [item["name"] for item in detail["path"]] == ["细胞膜", "膜运输"]
    assert detail["descendant_count"] == 0

    response = client.patch(
        f"/api/v1/chapters/{grandchild['id']}",
        json={"name": "原发性主动运输", "description": "依赖 ATP。"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "原发性主动运输"
    assert client.get(
        f"/api/v1/chapters/{grandchild['id']}"
    ).json()["description"] == "依赖 ATP。"

    response = client.patch(
        f"/api/v1/chapters/{child['id']}",
        json={"parent_id": None},
    )
    assert response.status_code == 200
    assert response.json()["parent_id"] is None

    tree = client.get(
        f"/api/v1/subjects/{subject['id']}/chapters"
    ).json()
    assert {node["name"] for node in tree} == {"细胞膜", "膜运输"}
    moved_child = next(node for node in tree if node["name"] == "膜运输")
    assert moved_child["children"][0]["name"] == "原发性主动运输"


def test_chapter_parent_validation_and_cycle_prevention(
    client: TestClient,
) -> None:
    subject_a = create_subject(client, "遗传学")
    subject_b = create_subject(client, "分子生物学")
    parent_in_b = create_chapter(client, subject_b["id"], "DNA 复制")

    response = client.post(
        f"/api/v1/subjects/{subject_a['id']}/chapters",
        json={"name": "跨学科错误", "parent_id": parent_in_b["id"]},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "parent_subject_mismatch"

    response = client.post(
        f"/api/v1/subjects/{subject_a['id']}/chapters",
        json={"name": "父级不存在", "parent_id": "missing-parent"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "parent_not_found"

    root = create_chapter(client, subject_a["id"], "一级")
    child = create_chapter(
        client,
        subject_a["id"],
        "二级",
        parent_id=root["id"],
    )
    grandchild = create_chapter(
        client,
        subject_a["id"],
        "三级",
        parent_id=child["id"],
    )

    response = client.patch(
        f"/api/v1/chapters/{root['id']}",
        json={"parent_id": root["id"]},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "chapter_cycle"

    response = client.patch(
        f"/api/v1/chapters/{root['id']}",
        json={"parent_id": grandchild["id"]},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "chapter_cycle"

    response = client.patch(
        f"/api/v1/chapters/{child['id']}",
        json={"parent_id": parent_in_b["id"]},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "parent_subject_mismatch"

    assert client.get(
        f"/api/v1/chapters/{root['id']}"
    ).json()["parent_id"] is None


def test_chapter_delete_protection_and_cascade(
    client: TestClient,
) -> None:
    subject = create_subject(client)
    root = create_chapter(client, subject["id"], "根章节")
    child = create_chapter(
        client,
        subject["id"],
        "子章节",
        parent_id=root["id"],
    )
    create_chapter(
        client,
        subject["id"],
        "孙章节",
        parent_id=child["id"],
    )

    response = client.delete(f"/api/v1/chapters/{root['id']}")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "chapter_has_children"
    assert response.json()["detail"]["descendant_count"] == 2

    assert client.get(f"/api/v1/chapters/{root['id']}").status_code == 200
    assert client.get(
        f"/api/v1/subjects/{subject['id']}"
    ).json()["chapter_count"] == 3

    response = client.delete(
        f"/api/v1/chapters/{root['id']}",
        params={"cascade": "true"},
    )
    assert response.status_code == 204
    assert client.get(f"/api/v1/chapters/{root['id']}").status_code == 404
    assert client.get(
        f"/api/v1/subjects/{subject['id']}/chapters"
    ).json() == []
    assert client.get(
        f"/api/v1/subjects/{subject['id']}"
    ).json()["chapter_count"] == 0


def test_chapter_move_reorders_siblings(client: TestClient) -> None:
    subject = create_subject(client)
    first = create_chapter(client, subject["id"], "第一节")
    second = create_chapter(client, subject["id"], "第二节")
    third = create_chapter(client, subject["id"], "第三节")

    def names() -> list[str]:
        return [
            node["name"]
            for node in client.get(
                f"/api/v1/subjects/{subject['id']}/chapters"
            ).json()
        ]

    assert names() == ["第一节", "第二节", "第三节"]

    response = client.post(
        f"/api/v1/chapters/{third['id']}/move",
        json={"direction": "up"},
    )
    assert response.status_code == 200
    assert names() == ["第一节", "第三节", "第二节"]

    response = client.post(
        f"/api/v1/chapters/{third['id']}/move",
        json={"direction": "up"},
    )
    assert response.status_code == 200
    assert names() == ["第三节", "第一节", "第二节"]

    response = client.post(
        f"/api/v1/chapters/{third['id']}/move",
        json={"direction": "up"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "cannot_move"

    response = client.post(
        f"/api/v1/chapters/{first['id']}/move",
        json={"direction": "down"},
    )
    assert response.status_code == 200
    assert names() == ["第三节", "第二节", "第一节"]


def test_chapter_errors_and_not_found(client: TestClient) -> None:
    subject = create_subject(client)

    response = client.get("/api/v1/chapters/missing")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "chapter_not_found"

    response = client.patch(
        "/api/v1/chapters/missing",
        json={"name": "不存在"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "chapter_not_found"

    response = client.delete("/api/v1/chapters/missing")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "chapter_not_found"

    response = client.get("/api/v1/subjects/missing/chapters")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "subject_not_found"

    response = client.post(
        f"/api/v1/subjects/{subject['id']}/chapters",
        json={"name": ""},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "validation_error"


def test_database_foreign_keys_cascade_and_persistence(
    client: TestClient,
    session_factory: sessionmaker,
    db_engine,
) -> None:
    subject = create_subject(client, "免疫学")
    root = create_chapter(client, subject["id"], "先天免疫")
    create_chapter(
        client,
        subject["id"],
        "屏障防御",
        parent_id=root["id"],
    )

    with session_factory() as db:
        assert db.get(Subject, subject["id"]) is not None
        assert db.scalar(select(func.count(Chapter.id))) == 2

        db.add(
            Chapter(
                subject_id="missing-subject",
                name="非法章节",
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        else:
            raise AssertionError("foreign key constraint was not enforced")

    new_engine = build_engine(f"sqlite:///{db_engine.url.database}")
    try:
        with sessionmaker(bind=new_engine, expire_on_commit=False)() as db:
            assert db.get(Subject, subject["id"]) is not None
            assert db.scalar(select(func.count(Chapter.id))) == 2
            db.delete(db.get(Subject, subject["id"]))
            db.commit()
            assert db.scalar(select(func.count(Chapter.id))) == 0
    finally:
        new_engine.dispose()
