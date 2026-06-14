import json
import shutil
from collections.abc import Iterable
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Artifact, Base, Item, Tag, Topic


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
