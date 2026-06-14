import json
import re
import shutil
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Artifact, BackupRun, Base, Item, Job, JobStatus, Tag, Topic
from app.services.jobs import enqueue_job


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _validate_artifact_paths(data_dir: Path, backup_dir: Path) -> tuple[Path, Path, Path]:
    resolved_data_dir = data_dir.resolve()
    resolved_backup_dir = backup_dir.resolve()
    resolved_target = (resolved_backup_dir / "data").resolve()

    if (
        resolved_target == resolved_data_dir
        or _is_relative_to(resolved_target, resolved_data_dir)
        or _is_relative_to(resolved_backup_dir, resolved_data_dir)
        or _is_relative_to(resolved_data_dir, resolved_target)
    ):
        raise ValueError("backup target overlaps data directory")

    return resolved_data_dir, resolved_backup_dir, resolved_target


def _iso_or_none(value) -> str | None:
    return value.isoformat() if value is not None else None


def _json_safe(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def _safe_label(label: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", label.strip()).strip("-")
    return safe or "backup"


def _new_backup_dir(backup_root: Path, label: str) -> tuple[Path, str]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base_name = f"{_safe_label(label)}-{timestamp}"
    for suffix in ["", *[f"-{index}" for index in range(2, 100)]]:
        name = f"{base_name}{suffix}"
        path = backup_root / name
        if not path.exists():
            return path, name
    raise RuntimeError("Unable to allocate unique backup directory")


def _safe_backup_subdir(relative_manifest_path: str | None) -> Path | None:
    if not relative_manifest_path:
        return None
    relative_path = Path(relative_manifest_path)
    if relative_path.is_absolute() or ".." in relative_path.parts or len(relative_path.parts) < 2:
        return None
    return Path(relative_path.parts[0])


def create_database_rows_snapshot(db: Session) -> dict[str, list[dict]]:
    snapshot: dict[str, list[dict]] = {}
    for table in Base.metadata.sorted_tables:
        rows = db.execute(select(table).order_by(*table.primary_key.columns)).mappings().all()
        snapshot[table.name] = [
            {column.name: _json_safe(row[column.name]) for column in table.columns}
            for row in rows
        ]
    return snapshot


def serialize_items(items: Iterable[Item]) -> list[dict]:
    return [
        {
            "id": item.id,
            "original_url": item.original_url,
            "normalized_url": item.normalized_url,
            "source_domain": item.source_domain,
            "title": item.title,
            "description": item.description,
            "body_text": item.body_text,
            "ai_summary": item.ai_summary,
            "ai_recommendation_reason": item.ai_recommendation_reason,
            "status": item.status.value,
            "classification_status": item.classification_status,
            "failure_reason": item.failure_reason,
            "saved_at": item.saved_at.isoformat(),
            "last_processed_at": _iso_or_none(item.last_processed_at),
        }
        for item in items
    ]


def serialize_artifacts(artifacts: Iterable[Artifact]) -> list[dict]:
    return [
        {
            "id": artifact.id,
            "item_id": artifact.item_id,
            "artifact_type": artifact.artifact_type.value,
            "path": artifact.path,
            "mime_type": artifact.mime_type,
            "created_at": artifact.created_at.isoformat(),
        }
        for artifact in artifacts
    ]


def serialize_topics(topics: Iterable[Topic]) -> list[dict]:
    return [
        {
            "id": topic.id,
            "name": topic.name,
            "parent_id": topic.parent_id,
            "confidence": topic.confidence,
        }
        for topic in topics
    ]


def serialize_tags(tags: Iterable[Tag]) -> list[dict]:
    return [{"id": tag.id, "name": tag.name} for tag in tags]


def create_backup_manifest(data_dir: Path, backup_dir: Path, database_dump_name: str) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    artifact_count = sum(1 for path in data_dir.rglob("*") if path.is_file()) if data_dir.exists() else 0
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "database_dump": database_dump_name,
        "artifact_file_count": artifact_count,
    }
    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def create_database_snapshot(backup_dir: Path, rows: dict[str, list[dict]]) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    path = backup_dir / "database.json"
    path.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    return path


def copy_artifacts(data_dir: Path, backup_dir: Path) -> Path:
    resolved_data_dir, resolved_backup_dir, target = _validate_artifact_paths(data_dir, backup_dir)
    if target.exists():
        shutil.rmtree(target)
    if resolved_data_dir.exists():
        shutil.copytree(resolved_data_dir, target)
    else:
        target.mkdir(parents=True)
    return target


def prune_completed_backups(db: Session, backup_root: Path, retention_count: int) -> list[Path]:
    if retention_count < 1:
        retention_count = 1

    completed_runs = db.scalars(
        select(BackupRun).where(BackupRun.status == "complete", BackupRun.path.is_not(None))
    ).all()
    completed_dirs = sorted(
        {
            backup_subdir
            for run in completed_runs
            if (backup_subdir := _safe_backup_subdir(run.path)) is not None
        },
        reverse=True,
    )
    pruned = completed_dirs[retention_count:]
    resolved_root = backup_root.resolve()
    for relative_dir in pruned:
        target = (resolved_root / relative_dir).resolve()
        if target.exists() and _is_relative_to(target, resolved_root) and target.is_dir():
            shutil.rmtree(target)
    return pruned


def enqueue_due_backup(db: Session, interval_hours: int) -> bool:
    if interval_hours < 1:
        return False

    active_job = db.scalar(
        select(Job).where(Job.job_type == "backup", Job.status.in_([JobStatus.queued, JobStatus.running]))
    )
    if active_job is not None:
        return False

    latest_run = db.scalar(select(BackupRun).order_by(BackupRun.created_at.desc()).limit(1))
    if latest_run is not None:
        created_at = latest_run.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if created_at + timedelta(hours=interval_hours) > datetime.now(timezone.utc):
            return False

    enqueue_job(db, "backup", payload={"reason": "scheduled"}, commit=False)
    db.commit()
    return True


def run_backup(
    db: Session,
    data_dir: Path,
    backup_dir: Path,
    label: str = "manual",
    retention_count: int | None = None,
) -> BackupRun:
    backup_root = backup_dir.resolve()
    backup_root.mkdir(parents=True, exist_ok=True)
    run_dir, run_name = _new_backup_dir(backup_root, label)
    manifest_relative_path = f"{run_name}/manifest.json"
    backup_run = BackupRun(status="running", path=manifest_relative_path, error=None)
    db.add(backup_run)
    db.flush()

    try:
        copy_artifacts(data_dir, run_dir)
        database = create_database_snapshot(run_dir, create_database_rows_snapshot(db))
        create_backup_manifest(data_dir, run_dir, database.name)
        backup_run.status = "complete"
        backup_run.error = None
        db.flush()
        if retention_count is not None:
            prune_completed_backups(db, backup_root, retention_count)
        return backup_run
    except Exception as exc:
        backup_run.status = "failed"
        backup_run.error = str(exc)
        if not run_dir.exists():
            backup_run.path = None
        db.flush()
        raise
