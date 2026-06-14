from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.core.config import get_settings
from app.db.models import Item, User
from app.db.session import get_db
from app.services.backup import copy_artifacts, create_backup_manifest, create_database_snapshot

router = APIRouter(prefix="/api/backups", tags=["backups"])


@router.post("/run")
def run_backup(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict[str, str]:
    settings = get_settings()
    backup_root = Path(settings.backup_dir) / "manual"
    copy_artifacts(Path(settings.data_dir), backup_root)
    items = db.scalars(select(Item)).all()
    database = create_database_snapshot(
        backup_root,
        {
            "items": [
                {
                    "id": item.id,
                    "original_url": item.original_url,
                    "normalized_url": item.normalized_url,
                    "source_domain": item.source_domain,
                    "title": item.title,
                    "status": item.status.value,
                    "saved_at": item.saved_at.isoformat(),
                }
                for item in items
            ]
        },
    )
    manifest = create_backup_manifest(Path(settings.data_dir), backup_root, database.name)
    return {"status": "complete", "manifest": str(manifest)}
