import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.services.backup import (
    copy_artifacts,
    create_backup_manifest,
    create_database_snapshot,
    prune_completed_backups,
    run_backup,
    serialize_artifacts,
    serialize_items,
)


def test_create_backup_manifest(tmp_path: Path):
    data_dir = tmp_path / "data"
    backup_dir = tmp_path / "backups"
    data_dir.mkdir()
    (data_dir / "sample.txt").write_text("saved", encoding="utf-8")

    database_path = create_database_snapshot(backup_dir=backup_dir, rows={"items": [{"id": "1"}]})
    manifest_path = create_backup_manifest(data_dir=data_dir, backup_dir=backup_dir, database_dump_name=database_path.name)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["database_dump"] == "database.json"
    assert manifest["artifact_file_count"] == 1
    assert json.loads(database_path.read_text(encoding="utf-8"))["items"] == [{"id": "1"}]


def test_copy_artifacts_replaces_existing_backup_data(tmp_path: Path):
    data_dir = tmp_path / "data"
    backup_dir = tmp_path / "backups"
    nested_dir = data_dir / "items"
    nested_dir.mkdir(parents=True)
    (nested_dir / "page.html").write_text("<h1>Saved</h1>", encoding="utf-8")
    stale_dir = backup_dir / "data"
    stale_dir.mkdir(parents=True)
    (stale_dir / "stale.txt").write_text("old", encoding="utf-8")

    target = copy_artifacts(data_dir=data_dir, backup_dir=backup_dir)

    assert (target / "items" / "page.html").read_text(encoding="utf-8") == "<h1>Saved</h1>"
    assert not (target / "stale.txt").exists()


def test_copy_artifacts_creates_empty_target_when_data_dir_is_missing(tmp_path: Path):
    target = copy_artifacts(data_dir=tmp_path / "missing", backup_dir=tmp_path / "backups")

    assert target.is_dir()
    assert list(target.iterdir()) == []


def test_copy_artifacts_rejects_backup_inside_source_without_deleting_source(tmp_path: Path):
    data_dir = tmp_path / "data"
    source_file = data_dir / "sample.txt"
    source_file.parent.mkdir()
    source_file.write_text("saved", encoding="utf-8")
    backup_dir = data_dir / "manual"
    (backup_dir / "data").mkdir(parents=True)

    with pytest.raises(ValueError, match="backup target overlaps data directory"):
        copy_artifacts(data_dir=data_dir, backup_dir=backup_dir)

    assert source_file.read_text(encoding="utf-8") == "saved"


def test_copy_artifacts_rejects_equal_source_and_target_without_deleting_source(tmp_path: Path):
    data_dir = tmp_path / "backup" / "data"
    source_file = data_dir / "sample.txt"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("saved", encoding="utf-8")

    with pytest.raises(ValueError, match="backup target overlaps data directory"):
        copy_artifacts(data_dir=data_dir, backup_dir=tmp_path / "backup")

    assert source_file.read_text(encoding="utf-8") == "saved"


def test_serialize_items_includes_full_item_columns():
    from app.db.models import Item, ItemStatus

    saved_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    processed_at = datetime(2026, 1, 3, 4, 5, 6, tzinfo=timezone.utc)
    item = Item(
        id="item-1",
        original_url="https://example.com/a?utm_source=x",
        normalized_url="https://example.com/a",
        source_domain="example.com",
        title="Example",
        description="Description",
        body_text="Body text",
        ai_summary="Summary",
        ai_recommendation_reason="Reason",
        status=ItemStatus.preserved,
        classification_status="complete",
        failure_reason=None,
        saved_at=saved_at,
        last_processed_at=processed_at,
    )

    snapshot = serialize_items([item])

    assert snapshot == [
        {
            "id": "item-1",
            "original_url": "https://example.com/a?utm_source=x",
            "normalized_url": "https://example.com/a",
            "source_domain": "example.com",
            "title": "Example",
            "description": "Description",
            "body_text": "Body text",
            "ai_summary": "Summary",
            "ai_recommendation_reason": "Reason",
            "status": "preserved",
            "classification_status": "complete",
            "failure_reason": None,
            "saved_at": saved_at.isoformat(),
            "last_processed_at": processed_at.isoformat(),
        }
    ]


def test_serialize_artifacts_includes_artifact_metadata():
    from app.db.models import Artifact, ArtifactType

    created_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    artifact = Artifact(
        id="artifact-1",
        item_id="item-1",
        artifact_type=ArtifactType.html,
        path="item-1/page.html",
        mime_type="text/html",
        created_at=created_at,
    )

    snapshot = serialize_artifacts([artifact])

    assert snapshot == [
        {
            "id": "artifact-1",
            "item_id": "item-1",
            "artifact_type": "html",
            "path": "item-1/page.html",
            "mime_type": "text/html",
            "created_at": created_at.isoformat(),
        }
    ]


def make_client(tmp_path: Path, monkeypatch) -> tuple[TestClient, sessionmaker]:
    database_url = f"sqlite+pysqlite:///{tmp_path.as_posix()}/backups.sqlite3"
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-value")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret-password")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))

    from app.core.config import get_settings

    get_settings.cache_clear()
    sys.modules.pop("app.api.auth", None)
    sys.modules.pop("app.api.backups", None)
    sys.modules.pop("app.main", None)
    sys.modules.pop("app.db.session", None)

    from app.db.init_db import bootstrap_database
    from app.db.models import Base

    engine = create_engine(database_url, future=True)
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


def test_run_backup_api_copies_artifacts_and_writes_item_snapshot(tmp_path: Path, monkeypatch):
    client, TestingSession = make_client(tmp_path, monkeypatch)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "sample.txt").write_text("saved", encoding="utf-8")

    from app.db.models import Artifact, ArtifactType, Item, ItemStatus

    with TestingSession() as session:
        session.add(
            Item(
                id="item-1",
                original_url="https://example.com/a?utm_source=x",
                normalized_url="https://example.com/a",
                source_domain="example.com",
                title="Example",
                body_text="Body text",
                status=ItemStatus.preserved,
            )
        )
        session.add(
            Artifact(
                id="artifact-1",
                item_id="item-1",
                artifact_type=ArtifactType.html,
                path="item-1/page.html",
                mime_type="text/html",
            )
        )
        session.commit()

    response = client.post("/api/backups/run")

    assert response.status_code == 200
    assert response.json()["status"] == "complete"
    assert response.json()["manifest"].endswith("/manifest.json")
    assert response.json()["manifest"] != "manual/manifest.json"
    manifest_path = tmp_path / "backups" / response.json()["manifest"]
    database_path = manifest_path.parent / "database.json"
    copied_artifact = manifest_path.parent / "data" / "sample.txt"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    database = json.loads(database_path.read_text(encoding="utf-8"))

    assert manifest["artifact_file_count"] == 1
    assert copied_artifact.read_text(encoding="utf-8") == "saved"
    assert database["items"][0]["id"] == "item-1"
    assert database["items"][0]["body_text"] == "Body text"
    assert database["items"][0]["status"] == "preserved"
    assert database["artifacts"][0]["id"] == "artifact-1"
    assert database["artifacts"][0]["artifact_type"] == "html"
    assert database["artifacts"][0]["path"] == "item-1/page.html"

    from app.db.models import BackupRun

    with TestingSession() as session:
        backup_run = session.query(BackupRun).one()

    assert backup_run.status == "complete"
    assert backup_run.path == response.json()["manifest"]
    assert backup_run.error is None


def test_run_backup_api_snapshots_all_database_tables(tmp_path: Path, monkeypatch):
    client, TestingSession = make_client(tmp_path, monkeypatch)
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    from app.db.models import BackupRun, Job, JobStatus

    with TestingSession() as session:
        session.add(Job(id="job-1", job_type="capture_item", status=JobStatus.queued, payload_json='{"kind": "test"}'))
        session.add(BackupRun(id="backup-run-1", status="complete", path="manual/manifest.json", error=None))
        session.commit()

    response = client.post("/api/backups/run")

    assert response.status_code == 200
    database_path = tmp_path / "backups" / response.json()["manifest"]
    database = json.loads((database_path.parent / "database.json").read_text(encoding="utf-8"))

    assert set(database) == {
        "users",
        "session_tokens",
        "topics",
        "tags",
        "items",
        "artifacts",
        "jobs",
        "backup_runs",
    }
    assert any(row["email"] == "admin@example.com" for row in database["users"])
    assert any(row["user_id"] for row in database["session_tokens"])
    assert any(row["id"] == "job-1" and row["status"] == "queued" for row in database["jobs"])
    assert any(row["id"] == "backup-run-1" and row["status"] == "complete" for row in database["backup_runs"])


def test_run_backup_service_writes_timestamped_dir_and_backup_run(tmp_path: Path):
    from app.db.models import BackupRun, Base

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path.as_posix()}/service.sqlite3", future=True)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, future=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "artifact.txt").write_text("saved", encoding="utf-8")

    with TestingSession() as session:
        backup_run = run_backup(session, data_dir, tmp_path / "backups", label="manual")
        run_status = backup_run.status
        run_path = backup_run.path
        run_error = backup_run.error
        session.commit()

    assert run_status == "complete"
    assert run_path is not None
    assert run_path.startswith("manual-")
    assert run_path.endswith("/manifest.json")
    assert run_error is None
    assert (tmp_path / "backups" / run_path).exists()

    with TestingSession() as session:
        persisted = session.query(BackupRun).one()

    assert persisted.status == "complete"
    assert persisted.path == run_path
    assert persisted.error is None


def test_backup_status_requires_authentication_and_admin_user(tmp_path: Path, monkeypatch):
    client, TestingSession = make_client(tmp_path, monkeypatch)

    client.cookies.clear()
    unauthenticated = client.get("/api/backups/status")

    assert unauthenticated.status_code == 401

    from app.db.init_db import pwd_context
    from app.db.models import User

    with TestingSession() as session:
        session.add(
            User(
                email="reader@example.com",
                password_hash=pwd_context.hash("secret-password"),
                is_admin=False,
            )
        )
        session.commit()

    client.post("/api/auth/login", json={"email": "reader@example.com", "password": "secret-password"})
    forbidden = client.get("/api/backups/status")

    assert forbidden.status_code == 403


def test_backup_status_returns_latest_runs_and_retention_config(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BACKUP_RETENTION_COUNT", "3")
    client, TestingSession = make_client(tmp_path, monkeypatch)

    from app.db.models import BackupRun

    with TestingSession() as session:
        session.add(BackupRun(id="old-run", status="failed", path=None, error="disk full"))
        session.commit()

    response = client.get("/api/backups/status")

    assert response.status_code == 200
    body = response.json()
    assert body["retention_count"] == 3
    assert body["interval_hours"] == 24
    assert body["runs"][0]["id"] == "old-run"
    assert body["runs"][0]["status"] == "failed"
    assert body["runs"][0]["path"] is None
    assert body["runs"][0]["error"] == "disk full"
    assert body["runs"][0]["created_at"]


def test_prune_completed_backups_keeps_latest_completed_dirs(tmp_path: Path):
    backup_root = tmp_path / "backups"
    for name in ["manual-20260101T000000Z", "manual-20260102T000000Z", "manual-20260103T000000Z"]:
        backup_dir = backup_root / name
        backup_dir.mkdir(parents=True)
        (backup_dir / "manifest.json").write_text("{}", encoding="utf-8")
    failed_dir = backup_root / "manual-20260104T000000Z"
    failed_dir.mkdir()
    (failed_dir / "manifest.json").write_text("{}", encoding="utf-8")

    from app.db.models import BackupRun, Base

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path.as_posix()}/retention.sqlite3", future=True)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, future=True)
    with TestingSession() as session:
        for name in ["manual-20260101T000000Z", "manual-20260102T000000Z", "manual-20260103T000000Z"]:
            session.add(BackupRun(status="complete", path=f"{name}/manifest.json", error=None))
        session.add(BackupRun(status="failed", path="manual-20260104T000000Z/manifest.json", error="boom"))
        session.commit()
        pruned = prune_completed_backups(session, backup_root, retention_count=2)

    assert pruned == [Path("manual-20260101T000000Z")]
    assert not (backup_root / "manual-20260101T000000Z").exists()
    assert (backup_root / "manual-20260102T000000Z").exists()
    assert (backup_root / "manual-20260103T000000Z").exists()
    assert failed_dir.exists()


def test_run_backup_requires_authentication(tmp_path: Path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    client.cookies.clear()

    response = client.post("/api/backups/run")

    assert response.status_code == 401


def test_run_backup_requires_admin_user(tmp_path: Path, monkeypatch):
    client, TestingSession = make_client(tmp_path, monkeypatch)

    from app.db.init_db import pwd_context
    from app.db.models import User

    with TestingSession() as session:
        session.add(
            User(
                email="reader@example.com",
                password_hash=pwd_context.hash("secret-password"),
                is_admin=False,
            )
        )
        session.commit()

    client.post("/api/auth/login", json={"email": "reader@example.com", "password": "secret-password"})
    response = client.post("/api/backups/run")

    assert response.status_code == 403
