from __future__ import annotations

from pydantic import BaseModel


class TopicNodeResponse(BaseModel):
    id: str
    name: str
    count: int
    children: list[TopicNodeResponse]


class TopicTreeResponse(BaseModel):
    topics: list[TopicNodeResponse]


class RecommendationItemResponse(BaseModel):
    id: str
    title: str
    source_domain: str
    summary: str | None
    reason: str
    topic: str
    status: str


class RecommendationListResponse(BaseModel):
    items: list[RecommendationItemResponse]
