import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


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
    target = backup_dir / "data"
    if target.exists():
        shutil.rmtree(target)
    if data_dir.exists():
        shutil.copytree(data_dir, target)
    else:
        target.mkdir(parents=True)
    return target
