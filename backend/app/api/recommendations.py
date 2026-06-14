from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.db.models import Item, User
from app.db.session import get_db
from app.schemas.ai import RecommendationListResponse
from app.services.ai import build_recommendation_reason, build_summary, suggest_topic_name

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("", response_model=RecommendationListResponse)
def recommendations(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    items = db.scalars(select(Item).order_by(Item.saved_at.desc()).limit(20)).all()
    return {
        "items": [
            {
                "id": item.id,
                "title": item.title or item.normalized_url,
                "source_domain": item.source_domain,
                "summary": build_summary(item),
                "reason": build_recommendation_reason(item),
                "topic": suggest_topic_name(item),
                "status": item.status.value,
            }
            for item in items
        ]
    }
