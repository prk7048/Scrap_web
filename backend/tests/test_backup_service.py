import importlib
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.services.backup import copy_artifacts, create_backup_manifest, create_database_snapshot


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

    from app.db.models import Item, ItemStatus

    with TestingSession() as session:
        session.add(
            Item(
                id="item-1",
                original_url="https://example.com/a?utm_source=x",
                normalized_url="https://example.com/a",
                source_domain="example.com",
                title="Example",
                status=ItemStatus.preserved,
            )
        )
        session.commit()

    response = client.post("/api/backups/run")

    assert response.status_code == 200
    assert response.json()["status"] == "complete"
    manifest_path = Path(response.json()["manifest"])
    database_path = manifest_path.parent / "database.json"
    copied_artifact = manifest_path.parent / "data" / "sample.txt"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    database = json.loads(database_path.read_text(encoding="utf-8"))

    assert manifest["artifact_file_count"] == 1
    assert copied_artifact.read_text(encoding="utf-8") == "saved"
    assert database["items"][0]["id"] == "item-1"
    assert database["items"][0]["status"] == "preserved"
