from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Item, ItemStatus
from app.services.jobs import enqueue_job
from app.services.url_normalize import normalize_url


def save_url(db: Session, url: str) -> tuple[Item, bool]:
    normalized = normalize_url(url)
    existing = db.scalar(select(Item).where(Item.normalized_url == normalized.normalized))
    if existing is not None:
        return existing, False

    item = Item(
        original_url=normalized.original,
        normalized_url=normalized.normalized,
        source_domain=normalized.domain,
        status=ItemStatus.queued,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    enqueue_job(db, "capture_item", item_id=item.id, payload={"item_id": item.id})
    return item, True


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


def retry_item(db: Session, item_id: str) -> Item:
    item = db.get(Item, item_id)
    if item is None:
        raise ValueError("Item not found")

    item.status = ItemStatus.queued
    item.failure_reason = None
    db.commit()
    db.refresh(item)
    enqueue_job(db, "capture_item", item_id=item.id, payload={"item_id": item.id})
    return item
