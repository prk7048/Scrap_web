from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.core.config import get_settings
from app.db.models import User
from app.db.session import get_db
from app.services.backup import (
    copy_artifacts,
    create_backup_manifest,
    create_database_rows_snapshot,
    create_database_snapshot,
)

router = APIRouter(prefix="/api/backups", tags=["backups"])


def current_admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


@router.post("/run")
def run_backup(db: Session = Depends(get_db), _: User = Depends(current_admin_user)) -> dict[str, str]:
    settings = get_settings()
    backup_name = "manual"
    backup_root = Path(settings.backup_dir) / backup_name
    copy_artifacts(Path(settings.data_dir), backup_root)
    database = create_database_snapshot(
        backup_root,
        create_database_rows_snapshot(db),
    )
    manifest = create_backup_manifest(Path(settings.data_dir), backup_root, database.name)
    return {"status": "complete", "manifest": f"{backup_name}/{manifest.name}"}
