from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl

from app.db.models import ItemStatus


class SaveUrlRequest(BaseModel):
    url: HttpUrl


class SaveManyRequest(BaseModel):
    urls: list[HttpUrl]


class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_url: str
    normalized_url: str
    source_domain: str
    title: str | None
    description: str | None
    status: ItemStatus
    classification_status: str
    failure_reason: str | None
    saved_at: datetime
    last_processed_at: datetime | None


class ItemListResponse(BaseModel):
    items: list[ItemResponse]
