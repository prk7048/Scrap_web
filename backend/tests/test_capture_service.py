import asyncio
import importlib
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Artifact, ArtifactType, Base, Item, ItemStatus, Job, JobStatus
from app.services.jobs import enqueue_job
from app.services.capture import CaptureResult, store_capture_result


def make_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "worker.sqlite3"
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-value")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret-password")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("DATA_DIR", (tmp_path / "data").as_posix())
    monkeypatch.setenv("BACKUP_DIR", (tmp_path / "backups").as_posix())

    from app.core.config import get_settings

    get_settings.cache_clear()
    sys.modules.pop("app.db.session", None)
    sys.modules.pop("app.worker", None)

    engine = create_engine(f"sqlite+pysqlite:///{db_path.as_posix()}", future=True)
    TestingSession = sessionmaker(bind=engine, future=True)
    Base.metadata.create_all(engine)

    worker = importlib.import_module("app.worker")
    worker.SessionLocal = TestingSession
    return worker, TestingSession


def test_store_capture_result_writes_artifacts(tmp_path: Path):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        item = Item(
            original_url="https://example.com",
            normalized_url="https://example.com",
            source_domain="example.com",
        )
        session.add(item)
        session.commit()
        session.refresh(item)

        store_capture_result(
            session,
            item,
            data_dir=tmp_path,
            title="Example",
            description="A page",
            body_text="Readable body",
            html="<html><body>Readable body</body></html>",
            screenshot_bytes=b"fake-png",
        )

        artifacts = session.scalars(select(Artifact).where(Artifact.item_id == item.id)).all()

    assert item.status == ItemStatus.preserved
    assert item.title == "Example"
    assert item.body_text == "Readable body"
    assert {artifact.artifact_type for artifact in artifacts} == {ArtifactType.html, ArtifactType.screenshot}
    assert all((tmp_path / artifact.path).exists() for artifact in artifacts)


def test_store_capture_result_preserves_partial_html_with_failure_reason(tmp_path: Path):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        item = Item(
            original_url="https://example.com",
            normalized_url="https://example.com",
            source_domain="example.com",
        )
        session.add(item)
        session.commit()
        session.refresh(item)

        store_capture_result(
            session,
            item,
            data_dir=tmp_path,
            title="Example",
            description="A page",
            body_text="Readable body",
            html="<html><body>Readable body</body></html>",
            screenshot_bytes=None,
            failure_reason="screenshot failed",
        )

        artifacts = session.scalars(select(Artifact).where(Artifact.item_id == item.id)).all()

    assert item.status == ItemStatus.classification_needed
    assert item.failure_reason == "screenshot failed"
    assert item.title == "Example"
    assert item.body_text == "Readable body"
    assert {artifact.artifact_type for artifact in artifacts} == {ArtifactType.html}
    assert all((tmp_path / artifact.path).exists() for artifact in artifacts)


def test_store_capture_result_preserves_html_when_screenshot_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        item = Item(
            original_url="https://example.com",
            normalized_url="https://example.com",
            source_domain="example.com",
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        item_id = item.id

        original_write_bytes = Path.write_bytes

        def fail_screenshot_write(path: Path, data: bytes) -> int:
            if path.name == "screenshot.png":
                raise OSError("disk full")
            return original_write_bytes(path, data)

        monkeypatch.setattr(Path, "write_bytes", fail_screenshot_write)

        store_capture_result(
            session,
            item,
            data_dir=tmp_path,
            title="Example",
            description="A page",
            body_text="Readable body",
            html="<html><body>Readable body</body></html>",
            screenshot_bytes=b"fake-png",
        )

    with Session(engine) as session:
        item = session.get(Item, item_id)
        artifacts = session.scalars(select(Artifact).where(Artifact.item_id == item_id)).all()

    assert item.status == ItemStatus.classification_needed
    assert item.failure_reason == "disk full"
    assert item.body_text == "Readable body"
    assert {artifact.artifact_type for artifact in artifacts} == {ArtifactType.html}
    assert all((tmp_path / artifact.path).exists() for artifact in artifacts)


def test_store_capture_result_accepts_relative_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        item = Item(
            original_url="https://example.com",
            normalized_url="https://example.com",
            source_domain="example.com",
        )
        session.add(item)
        session.commit()
        session.refresh(item)

        store_capture_result(
            session,
            item,
            data_dir=Path("data"),
            title="Example",
            description="A page",
            body_text="Readable body",
            html="<html><body>Readable body</body></html>",
            screenshot_bytes=b"fake-png",
        )

        artifacts = session.scalars(select(Artifact).where(Artifact.item_id == item.id)).all()

    artifact_paths = {Path(artifact.path) for artifact in artifacts}
    assert artifact_paths == {
        Path("items") / item.id / "snapshot.html",
        Path("items") / item.id / "screenshot.png",
    }
    assert all(not artifact_path.is_absolute() for artifact_path in artifact_paths)
    assert all((tmp_path / "data" / artifact_path).exists() for artifact_path in artifact_paths)


def test_store_capture_result_rejects_traversal_item_id(tmp_path: Path):
    data_dir = tmp_path / "data"
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        item = Item(
            id="../escape",
            original_url="https://example.com",
            normalized_url="https://example.com",
            source_domain="example.com",
        )
        session.add(item)
        session.commit()
        session.refresh(item)

        with pytest.raises(ValueError, match="Invalid item id"):
            store_capture_result(
                session,
                item,
                data_dir=data_dir,
                title="Example",
                description=None,
                body_text="Readable body",
                html="<html></html>",
                screenshot_bytes=b"fake-png",
            )

    assert not (tmp_path / "escape").exists()
    assert not data_dir.exists()


def test_run_once_fails_unsupported_job_type(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    worker, TestingSession = make_worker(tmp_path, monkeypatch)

    with TestingSession() as session:
        job = enqueue_job(session, "unsupported")
        job_id = job.id

    did_work = asyncio.run(worker.run_once())

    with TestingSession() as session:
        job = session.get(Job, job_id)

    assert did_work is True
    assert job.status == JobStatus.failed
    assert "Unsupported job type" in job.error


def test_run_once_fails_capture_job_without_item_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    worker, TestingSession = make_worker(tmp_path, monkeypatch)

    with TestingSession() as session:
        job = enqueue_job(session, "capture_item")
        job_id = job.id

    did_work = asyncio.run(worker.run_once())

    with TestingSession() as session:
        job = session.get(Job, job_id)

    assert did_work is True
    assert job.status == JobStatus.failed
    assert "missing item_id" in job.error


def test_run_once_fails_capture_job_when_item_is_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    worker, TestingSession = make_worker(tmp_path, monkeypatch)

    missing_item_id = "00000000-0000-0000-0000-000000000000"
    with TestingSession() as session:
        job = enqueue_job(session, "capture_item", item_id=missing_item_id)
        job_id = job.id

    did_work = asyncio.run(worker.run_once())

    with TestingSession() as session:
        job = session.get(Job, job_id)

    assert did_work is True
    assert job.status == JobStatus.failed
    assert f"capture_item job item not found: {missing_item_id}" in job.error


def test_run_once_processes_backup_job(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    worker, TestingSession = make_worker(tmp_path, monkeypatch)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "saved.txt").write_text("saved", encoding="utf-8")

    with TestingSession() as session:
        job = enqueue_job(session, "backup")
        job_id = job.id

    did_work = asyncio.run(worker.run_once())

    from app.db.models import BackupRun

    with TestingSession() as session:
        job = session.get(Job, job_id)
        backup_run = session.query(BackupRun).one()

    assert did_work is True
    assert job.status == JobStatus.complete
    assert backup_run.status == "complete"
    assert backup_run.path is not None
    assert backup_run.path.startswith("auto-")
    assert (tmp_path / "backups" / backup_run.path).exists()


def test_run_once_marks_item_and_job_failed_when_capture_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    worker, TestingSession = make_worker(tmp_path, monkeypatch)

    async def fail_capture(url: str, timeout_ms: int):
        raise RuntimeError("capture exploded")

    monkeypatch.setattr(worker, "capture_url", fail_capture)

    with TestingSession() as session:
        item = Item(
            original_url="https://example.com",
            normalized_url="https://example.com",
            source_domain="example.com",
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        job = enqueue_job(session, "capture_item", item_id=item.id)
        item_id = item.id
        job_id = job.id

    did_work = asyncio.run(worker.run_once())

    with TestingSession() as session:
        item = session.get(Item, item_id)
        job = session.get(Job, job_id)

    assert did_work is True
    assert item.status == ItemStatus.failed
    assert item.failure_reason == "capture exploded"
    assert job.status == JobStatus.failed
    assert job.error == "capture exploded"


def test_run_once_preserves_partial_capture_when_later_artifact_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    worker, TestingSession = make_worker(tmp_path, monkeypatch)

    async def partial_capture(url: str, timeout_ms: int):
        return CaptureResult(
            title="Example",
            description="A page",
            body_text="Readable body",
            html="<html><body>Readable body</body></html>",
            screenshot_bytes=None,
            failure_reason="screenshot exploded",
        )

    monkeypatch.setattr(worker, "capture_url", partial_capture)

    with TestingSession() as session:
        item = Item(
            original_url="https://example.com",
            normalized_url="https://example.com",
            source_domain="example.com",
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        job = enqueue_job(session, "capture_item", item_id=item.id)
        item_id = item.id
        job_id = job.id

    did_work = asyncio.run(worker.run_once())

    with TestingSession() as session:
        item = session.get(Item, item_id)
        job = session.get(Job, job_id)
        artifacts = session.scalars(select(Artifact).where(Artifact.item_id == item_id)).all()

    assert did_work is True
    assert item.status == ItemStatus.classification_needed
    assert item.failure_reason == "screenshot exploded"
    assert item.title == "Example"
    assert item.body_text == "Readable body"
    assert job.status == JobStatus.complete
    assert job.error is None
    assert {artifact.artifact_type for artifact in artifacts} == {ArtifactType.html}
    assert all((tmp_path / "data" / artifact.path).exists() for artifact in artifacts)
