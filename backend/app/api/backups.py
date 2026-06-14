from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.core.config import get_settings
from app.db.models import BackupRun, User
from app.db.session import get_db
from app.services.backup import run_backup as execute_backup

router = APIRouter(prefix="/api/backups", tags=["backups"])


def current_admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


@router.post("/run")
def run_backup(db: Session = Depends(get_db), _: User = Depends(current_admin_user)) -> dict[str, str | None]:
    settings = get_settings()
    try:
        backup_run = execute_backup(
            db,
            Path(settings.data_dir),
            Path(settings.backup_dir),
            label="manual",
            retention_count=settings.backup_retention_count,
        )
        db.commit()
        db.refresh(backup_run)
    except Exception as exc:
        db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return {"status": backup_run.status, "manifest": backup_run.path}


@router.get("/status")
def backup_status(db: Session = Depends(get_db), _: User = Depends(current_admin_user)) -> dict:
    settings = get_settings()
    runs = db.scalars(select(BackupRun).order_by(BackupRun.created_at.desc()).limit(10)).all()
    return {
        "retention_count": settings.backup_retention_count,
        "interval_hours": settings.backup_interval_hours,
        "runs": [
            {
                "id": run.id,
                "status": run.status,
                "path": run.path,
                "error": run.error,
                "created_at": run.created_at.isoformat(),
            }
            for run in runs
        ],
    }
