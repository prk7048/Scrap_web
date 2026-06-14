import importlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker


def make_client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-value")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret-password")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path.as_posix()}/items.sqlite3")
    monkeypatch.setenv("DATA_DIR", (tmp_path / "data").as_posix())

    from app.core.config import get_settings

    get_settings.cache_clear()
    sys.modules.pop("app.api.auth", None)
    sys.modules.pop("app.api.items", None)
    sys.modules.pop("app.main", None)
    sys.modules.pop("app.db.session", None)

    from app.db.init_db import bootstrap_database
    from app.db.models import Base

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path.as_posix()}/items.sqlite3", future=True)
    TestingSession = sessionmaker(bind=engine, future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        bootstrap_database(session, "admin@example.com", "secret-password")

    session_module = importlib.import_module("app.db.session")
    main = importlib.import_module("app.main")

    def override_db():
        with TestingSession() as session:
            yield session

    app = main.create_app()
    app.dependency_overrides[session_module.get_db] = override_db
    client = TestClient(app)
    client.post("/api/auth/login", json={"email": "admin@example.com", "password": "secret-password"})
    return client, TestingSession


def test_save_url_creates_item_and_capture_job(tmp_path, monkeypatch):
    client, TestingSession = make_client(tmp_path, monkeypatch)
    response = client.post("/api/items/save", json={"url": "https://example.com/a?utm_source=x"})
    assert response.status_code == 201

    from app.db.models import Item, Job

    with TestingSession() as session:
        item = session.scalar(select(Item))
        job = session.scalar(select(Job))

    assert item.normalized_url == "https://example.com/a"
    assert job.job_type == "capture_item"
    assert job.item_id == item.id


def test_save_duplicate_returns_existing_item(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    first = client.post("/api/items/save", json={"url": "https://example.com/a"}).json()
    second_response = client.post("/api/items/save", json={"url": "https://example.com/a?utm_campaign=x"})
    assert second_response.status_code == 200
    assert second_response.json()["id"] == first["id"]


def test_extension_token_can_save_url_without_session_cookie(tmp_path, monkeypatch):
    client, TestingSession = make_client(tmp_path, monkeypatch)
    token_response = client.post("/api/auth/extension-token")
    token = token_response.json()["token"]
    client.cookies.clear()

    response = client.post(
        "/api/items/save",
        headers={"Authorization": f"Bearer {token}"},
        json={"url": "https://example.com/from-extension"},
    )

    assert response.status_code == 201

    from app.db.models import Item

    with TestingSession() as session:
        item = session.scalar(select(Item))

    assert item.normalized_url == "https://example.com/from-extension"


def test_extension_token_can_save_many_without_session_cookie(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    token_response = client.post("/api/auth/extension-token")
    token = token_response.json()["token"]
    client.cookies.clear()

    response = client.post(
        "/api/items/save-many",
        headers={"Authorization": f"Bearer {token}"},
        json={"urls": ["https://example.com/one", "https://example.com/two"]},
    )

    assert response.status_code == 201
    assert [item["normalized_url"] for item in response.json()["items"]] == [
        "https://example.com/one",
        "https://example.com/two",
    ]


def test_extension_token_cannot_access_full_item_endpoints(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    token_response = client.post("/api/auth/extension-token")
    token = token_response.json()["token"]
    client.cookies.clear()

    response = client.get("/api/items", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_get_item_detail_includes_body_text_and_artifacts(tmp_path, monkeypatch):
    client, TestingSession = make_client(tmp_path, monkeypatch)

    from app.db.models import Artifact, ArtifactType, Item, ItemStatus

    with TestingSession() as session:
        item = Item(
            original_url="https://example.com/article?utm_source=x",
            normalized_url="https://example.com/article",
            source_domain="example.com",
            title="Readable Article",
            description="A compact archive entry",
            body_text="Full readable body",
            ai_summary="Short summary",
            ai_recommendation_reason="Useful later",
            status=ItemStatus.preserved,
            classification_status="complete",
        )
        session.add(item)
        session.flush()
        artifact = Artifact(
            item_id=item.id,
            artifact_type=ArtifactType.html,
            path=str(Path("items") / item.id / "snapshot.html"),
            mime_type="text/html",
        )
        session.add(artifact)
        session.commit()
        item_id = item.id
        artifact_id = artifact.id

    response = client.get(f"/api/items/{item_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == item_id
    assert data["body_text"] == "Full readable body"
    assert data["ai_summary"] == "Short summary"
    assert data["ai_recommendation_reason"] == "Useful later"
    assert data["artifacts"] == [
        {
            "id": artifact_id,
            "type": "html",
            "path": f"items/{item_id}/snapshot.html",
            "mime_type": "text/html",
            "created_at": data["artifacts"][0]["created_at"],
        }
    ]


def test_get_items_filters_by_topic_source_date_status_and_failure(tmp_path, monkeypatch):
    client, TestingSession = make_client(tmp_path, monkeypatch)

    from app.db.models import Item, ItemStatus

    old_date = datetime(2026, 1, 2, tzinfo=timezone.utc)
    recent_date = old_date + timedelta(days=3)
    with TestingSession() as session:
        session.add_all(
            [
                Item(
                    original_url="https://openai.com/research",
                    normalized_url="https://openai.com/research",
                    source_domain="openai.com",
                    title="Model research",
                    body_text="prompt and agent notes",
                    status=ItemStatus.preserved,
                    failure_reason=None,
                    saved_at=recent_date,
                ),
                Item(
                    original_url="https://docs.python.org/tutorial",
                    normalized_url="https://docs.python.org/tutorial",
                    source_domain="docs.python.org",
                    title="Python tutorial",
                    body_text="development notes",
                    status=ItemStatus.failed,
                    failure_reason="body extraction failed",
                    saved_at=old_date,
                ),
                Item(
                    original_url="https://example.com/cooking",
                    normalized_url="https://example.com/cooking",
                    source_domain="example.com",
                    title="Cooking notes",
                    body_text="recipes",
                    status=ItemStatus.inbox,
                    failure_reason=None,
                    saved_at=old_date,
                ),
            ]
        )
        session.commit()

    topic_response = client.get("/api/items", params={"topic": "AI"})
    source_response = client.get("/api/items", params={"source": "python.org"})
    domain_alias_response = client.get("/api/items", params={"domain": "python.org"})
    date_response = client.get(
        "/api/items",
        params={"date_from": recent_date.isoformat(), "date_to": recent_date.isoformat()},
    )
    status_response = client.get("/api/items", params={"status": "failed"})
    capture_status_alias_response = client.get("/api/items", params={"capture_status": "failed"})
    failure_response = client.get("/api/items", params={"has_failure": "true"})
    no_failure_response = client.get("/api/items", params={"has_failure": "false"})
    source_topic_response = client.get("/api/items", params={"topic": "source:openai.com"})

    assert [item["source_domain"] for item in topic_response.json()["items"]] == ["openai.com"]
    assert [item["source_domain"] for item in source_response.json()["items"]] == ["docs.python.org"]
    assert [item["source_domain"] for item in domain_alias_response.json()["items"]] == ["docs.python.org"]
    assert [item["source_domain"] for item in date_response.json()["items"]] == ["openai.com"]
    assert [item["source_domain"] for item in status_response.json()["items"]] == ["docs.python.org"]
    assert [item["source_domain"] for item in capture_status_alias_response.json()["items"]] == ["docs.python.org"]
    assert [item["source_domain"] for item in failure_response.json()["items"]] == ["docs.python.org"]
    assert [item["source_domain"] for item in no_failure_response.json()["items"]] == ["openai.com", "example.com"]
    assert [item["source_domain"] for item in source_topic_response.json()["items"]] == ["openai.com"]


def test_get_items_keyword_search_includes_source_domain(tmp_path, monkeypatch):
    client, TestingSession = make_client(tmp_path, monkeypatch)

    from app.db.models import Item, ItemStatus

    with TestingSession() as session:
        session.add_all(
            [
                Item(
                    original_url="https://news.ycombinator.com/item?id=1",
                    normalized_url="https://news.ycombinator.com/item?id=1",
                    source_domain="news.ycombinator.com",
                    title="Discussion",
                    body_text="comments",
                    status=ItemStatus.preserved,
                ),
                Item(
                    original_url="https://example.com/other",
                    normalized_url="https://example.com/other",
                    source_domain="example.com",
                    title="Other",
                    body_text="unrelated",
                    status=ItemStatus.preserved,
                ),
            ]
        )
        session.commit()

    response = client.get("/api/items", params={"q": "ycombinator"})

    assert response.status_code == 200
    assert [item["source_domain"] for item in response.json()["items"]] == ["news.ycombinator.com"]


def test_get_item_artifact_returns_file(tmp_path, monkeypatch):
    client, TestingSession = make_client(tmp_path, monkeypatch)

    from app.db.models import Artifact, ArtifactType, Item, ItemStatus

    data_dir = tmp_path / "data"
    with TestingSession() as session:
        item = Item(
            original_url="https://example.com/article",
            normalized_url="https://example.com/article",
            source_domain="example.com",
            status=ItemStatus.preserved,
        )
        session.add(item)
        session.flush()
        relative_path = Path("items") / item.id / "snapshot.html"
        artifact_path = data_dir / relative_path
        artifact_path.parent.mkdir(parents=True)
        artifact_path.write_text("<html><body>Saved</body></html>", encoding="utf-8")
        artifact = Artifact(
            item_id=item.id,
            artifact_type=ArtifactType.html,
            path=str(relative_path),
            mime_type="text/html",
        )
        session.add(artifact)
        session.commit()
        item_id = item.id
        artifact_id = artifact.id

    response = client.get(f"/api/items/{item_id}/artifacts/{artifact_id}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text == "<html><body>Saved</body></html>"


def test_get_item_artifact_rejects_traversal_path(tmp_path, monkeypatch):
    client, TestingSession = make_client(tmp_path, monkeypatch)

    from app.db.models import Artifact, ArtifactType, Item

    with TestingSession() as session:
        item = Item(
            original_url="https://example.com/article",
            normalized_url="https://example.com/article",
            source_domain="example.com",
        )
        session.add(item)
        session.flush()
        artifact = Artifact(
            item_id=item.id,
            artifact_type=ArtifactType.html,
            path=str(Path("..") / "escape.html"),
            mime_type="text/html",
        )
        session.add(artifact)
        session.commit()
        item_id = item.id
        artifact_id = artifact.id

    response = client.get(f"/api/items/{item_id}/artifacts/{artifact_id}")

    assert response.status_code == 400


def test_item_detail_and_artifacts_require_authentication(tmp_path, monkeypatch):
    client, TestingSession = make_client(tmp_path, monkeypatch)

    from app.db.models import Artifact, ArtifactType, Item

    with TestingSession() as session:
        item = Item(
            original_url="https://example.com/article",
            normalized_url="https://example.com/article",
            source_domain="example.com",
        )
        session.add(item)
        session.flush()
        artifact = Artifact(
            item_id=item.id,
            artifact_type=ArtifactType.html,
            path=str(Path("items") / item.id / "snapshot.html"),
            mime_type="text/html",
        )
        session.add(artifact)
        session.commit()
        item_id = item.id
        artifact_id = artifact.id

    client.cookies.clear()

    detail_response = client.get(f"/api/items/{item_id}")
    artifact_response = client.get(f"/api/items/{item_id}/artifacts/{artifact_id}")

    assert detail_response.status_code == 401
    assert artifact_response.status_code == 401


def test_get_item_artifact_returns_404_for_another_items_artifact(tmp_path, monkeypatch):
    client, TestingSession = make_client(tmp_path, monkeypatch)

    from app.db.models import Artifact, ArtifactType, Item

    with TestingSession() as session:
        first = Item(
            original_url="https://example.com/first",
            normalized_url="https://example.com/first",
            source_domain="example.com",
        )
        second = Item(
            original_url="https://example.com/second",
            normalized_url="https://example.com/second",
            source_domain="example.com",
        )
        session.add_all([first, second])
        session.flush()
        second_artifact = Artifact(
            item_id=second.id,
            artifact_type=ArtifactType.html,
            path=str(Path("items") / second.id / "snapshot.html"),
            mime_type="text/html",
        )
        session.add(second_artifact)
        session.commit()
        first_id = first.id
        second_artifact_id = second_artifact.id

    response = client.get(f"/api/items/{first_id}/artifacts/{second_artifact_id}")

    assert response.status_code == 404


def test_save_url_rolls_back_item_when_enqueue_fails(tmp_path, monkeypatch):
    _, TestingSession = make_client(tmp_path, monkeypatch)

    def fail_enqueue(*args, **kwargs):
        raise RuntimeError("queue unavailable")

    import app.services.items as item_service
    from app.db.models import Item

    monkeypatch.setattr(item_service, "enqueue_job", fail_enqueue)

    with TestingSession() as session:
        try:
            item_service.save_url(session, "https://example.com/b")
        except RuntimeError as exc:
            assert str(exc) == "queue unavailable"
        else:
            raise AssertionError("save_url should raise when enqueue fails")

        assert session.scalar(select(Item)) is None


def test_save_url_recovers_existing_item_after_integrity_error(tmp_path, monkeypatch):
    _, TestingSession = make_client(tmp_path, monkeypatch)

    import app.services.items as item_service
    from app.db.models import Item

    with TestingSession() as session:
        existing, created = item_service.save_url(session, "https://example.com/c")
        assert created is True

    with TestingSession() as session:
        original_scalar = session.scalar
        first_lookup = True

        def miss_then_select(*args, **kwargs):
            nonlocal first_lookup
            if first_lookup:
                first_lookup = False
                return None
            return original_scalar(*args, **kwargs)

        monkeypatch.setattr(session, "scalar", miss_then_select)

        item, created = item_service.save_url(session, "https://example.com/c")

    assert created is False
    assert item.id == existing.id


def test_claim_next_job_marks_one_queued_job_running(tmp_path, monkeypatch):
    _, TestingSession = make_client(tmp_path, monkeypatch)

    from app.db.models import JobStatus
    from app.services.jobs import claim_next_job, enqueue_job

    with TestingSession() as session:
        enqueue_job(session, "capture_item")
        first = claim_next_job(session)
        second = claim_next_job(session)

    assert first is not None
    assert first.status == JobStatus.running
    assert first.attempts == 1
    assert second is None


def test_claim_next_job_continues_when_first_candidate_is_lost(tmp_path, monkeypatch):
    _, TestingSession = make_client(tmp_path, monkeypatch)

    from app.db.models import Job, JobStatus
    from app.services.jobs import claim_next_job, enqueue_job

    with TestingSession() as setup_session:
        lost = enqueue_job(setup_session, "capture_item")
        next_job = enqueue_job(setup_session, "capture_item")
        lost_id = lost.id
        next_id = next_job.id

    with TestingSession() as session:
        original_execute = session.execute
        lost_once = False

        def lose_first_candidate(statement, *args, **kwargs):
            nonlocal lost_once
            if not lost_once and statement.is_update:
                lost_once = True
                with TestingSession() as competing_session:
                    competing_job = competing_session.get(Job, lost_id)
                    competing_job.status = JobStatus.running
                    competing_job.attempts += 1
                    competing_session.commit()
            return original_execute(statement, *args, **kwargs)

        monkeypatch.setattr(session, "execute", lose_first_candidate)

        claimed = claim_next_job(session)

    assert claimed is not None
    assert claimed.id == next_id
    assert claimed.status == JobStatus.running
    assert claimed.attempts == 1


def test_claim_next_job_continues_after_more_than_five_lost_candidates(tmp_path, monkeypatch):
    _, TestingSession = make_client(tmp_path, monkeypatch)

    from app.db.models import Job, JobStatus
    from app.services.jobs import claim_next_job, enqueue_job

    with TestingSession() as setup_session:
        job_ids = [enqueue_job(setup_session, "capture_item").id for _ in range(7)]
        expected_id = job_ids[-1]

    with TestingSession() as session:
        original_execute = session.execute
        lost_count = 0

        def lose_six_candidates(statement, *args, **kwargs):
            nonlocal lost_count
            if lost_count < 6 and statement.is_update:
                lost_count += 1
                with TestingSession() as competing_session:
                    competing_job = competing_session.get(Job, job_ids[lost_count - 1])
                    competing_job.status = JobStatus.running
                    competing_job.attempts += 1
                    competing_session.commit()
            return original_execute(statement, *args, **kwargs)

        monkeypatch.setattr(session, "execute", lose_six_candidates)

        claimed = claim_next_job(session)

    assert claimed is not None
    assert claimed.id == expected_id
    assert claimed.status == JobStatus.running
    assert claimed.attempts == 1
