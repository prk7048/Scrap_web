from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.models import Artifact, Item, ItemStatus
from app.services.jobs import enqueue_job
from app.services.url_normalize import normalize_url


def save_url(db: Session, url: str) -> tuple[Item, bool]:
    normalized = normalize_url(url)
    existing = db.scalar(select(Item).where(Item.normalized_url == normalized.normalized))
    if existing is not None:
        return existing, False

    try:
        item = Item(
            original_url=normalized.original,
            normalized_url=normalized.normalized,
            source_domain=normalized.domain,
            status=ItemStatus.queued,
        )
        db.add(item)
        db.flush()
        enqueue_job(db, "capture_item", item_id=item.id, payload={"item_id": item.id}, commit=False)
        db.commit()
        db.refresh(item)
        return item, True
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Item).where(Item.normalized_url == normalized.normalized))
        if existing is None:
            raise
        return existing, False
    except Exception:
        db.rollback()
        raise


def list_items(db: Session, query: str | None = None, status: ItemStatus | None = None) -> list[Item]:
    statement = select(Item).order_by(Item.saved_at.desc())
    if status is not None:
        statement = statement.where(Item.status == status)
    if query:
        search = f"%{query}%"
        statement = statement.where(
            or_(
                Item.title.ilike(search),
                Item.normalized_url.ilike(search),
                Item.body_text.ilike(search),
            )
        )
    return list(db.scalars(statement))


def get_item(db: Session, item_id: str) -> Item | None:
    return db.scalar(select(Item).options(selectinload(Item.artifacts)).where(Item.id == item_id))


def get_item_artifact(db: Session, item_id: str, artifact_id: str) -> tuple[Item, Artifact] | None:
    item = db.get(Item, item_id)
    if item is None:
        return None
    artifact = db.scalar(select(Artifact).where(Artifact.id == artifact_id, Artifact.item_id == item_id))
    if artifact is None:
        return None
    return item, artifact


def resolve_artifact_path(data_dir: Path, artifact: Artifact) -> Path:
    base_dir = data_dir.resolve()
    artifact_path = Path(artifact.path)
    if artifact_path.is_absolute():
        raise ValueError("Artifact path must be relative")

    resolved_path = (base_dir / artifact_path).resolve()
    if not resolved_path.is_relative_to(base_dir):
        raise ValueError("Artifact path escapes data directory")
    if not resolved_path.is_file():
        raise FileNotFoundError("Artifact file not found")
    return resolved_path


def retry_item(db: Session, item_id: str) -> Item:
    item = db.get(Item, item_id)
    if item is None:
        raise ValueError("Item not found")

    try:
        item.status = ItemStatus.queued
        item.failure_reason = None
        enqueue_job(db, "capture_item", item_id=item.id, payload={"item_id": item.id}, commit=False)
        db.commit()
        db.refresh(item)
        return item
    except Exception:
        db.rollback()
        raise
