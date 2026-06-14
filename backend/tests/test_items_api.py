import importlib
import sys

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker


def make_client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-value")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret-password")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path.as_posix()}/items.sqlite3")

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
