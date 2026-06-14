from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_serializer

from app.db.models import ArtifactType, ItemStatus


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


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: ArtifactType = Field(validation_alias="artifact_type")
    path: str
    mime_type: str
    created_at: datetime

    @field_serializer("path")
    def serialize_path(self, path: str) -> str:
        return path.replace("\\", "/")


class ItemDetailResponse(ItemResponse):
    body_text: str | None
    ai_summary: str | None
    ai_recommendation_reason: str | None
    artifacts: list[ArtifactResponse]


class ItemListResponse(BaseModel):
    items: list[ItemResponse]
