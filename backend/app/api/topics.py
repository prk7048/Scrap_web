from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.db.models import Item, User
from app.db.session import get_db
from app.services.ai import suggest_topic_name

router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.get("/tree")
def topic_tree(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    counts: dict[str, int] = {}
    for item in db.scalars(select(Item)).all():
        topic = suggest_topic_name(item)
        counts[topic] = counts.get(topic, 0) + 1
    return {
        "topics": [
            {"id": name.lower(), "name": name, "count": count, "children": []}
            for name, count in sorted(counts.items())
        ]
    }
