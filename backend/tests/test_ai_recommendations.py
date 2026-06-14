import importlib
import sys
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Item, ItemStatus
from app.services.ai import build_recommendation_reason, suggest_topic_name


def make_client(tmp_path, monkeypatch, *, login: bool = True):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-value")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret-password")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path.as_posix()}/ai.sqlite3")

    from app.core.config import get_settings

    get_settings.cache_clear()
    sys.modules.pop("app.api.auth", None)
    sys.modules.pop("app.api.recommendations", None)
    sys.modules.pop("app.api.topics", None)
    sys.modules.pop("app.main", None)
    sys.modules.pop("app.db.session", None)

    from app.db.init_db import bootstrap_database
    from app.db.models import Base

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path.as_posix()}/ai.sqlite3", future=True)
    TestingSession = sessionmaker(bind=engine, future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        bootstrap_database(session, "admin@example.com", "secret-password")

    session_module = importlib.import_module("app.db.session")
    main = importlib.import_module("app.main")

    def override_db():
        with TestingSession() as session:
            yield session

    app = main.create_app()
    app.dependency_overrides[session_module.get_db] = override_db
    client = TestClient(app)
    if login:
        client.post("/api/auth/login", json={"email": "admin@example.com", "password": "secret-password"})
    return client, TestingSession


def test_suggest_topic_name_uses_content_keywords():
    item = Item(
        original_url="https://example.com",
        normalized_url="https://example.com",
        source_domain="example.com",
        title="Local LLM on Ubuntu",
        body_text="Run local AI models on Ubuntu with GPU support.",
        status=ItemStatus.preserved,
    )
    assert suggest_topic_name(item) == "AI"


def test_suggest_topic_name_does_not_match_ai_inside_words():
    item = Item(
        original_url="https://example.com",
        normalized_url="https://example.com",
        source_domain="example.com",
        title="Plain mail training notes",
        body_text="A practical guide for team workflows.",
        status=ItemStatus.preserved,
    )
    assert suggest_topic_name(item) == "Unsorted"


def test_suggest_topic_name_matches_standalone_ai():
    item = Item(
        original_url="https://example.com",
        normalized_url="https://example.com",
        source_domain="example.com",
        title="AI field notes",
        status=ItemStatus.preserved,
    )
    assert suggest_topic_name(item) == "AI"


def test_suggest_topic_name_matches_openai_domain():
    item = Item(
        original_url="https://openai.com",
        normalized_url="https://openai.com",
        source_domain="openai.com",
        title="Research notes",
        status=ItemStatus.preserved,
    )
    assert suggest_topic_name(item) == "AI"


def test_recommendation_reason_mentions_recent_saved_item():
    item = Item(
        original_url="https://example.com",
        normalized_url="https://example.com",
        source_domain="example.com",
        title="Example",
        status=ItemStatus.preserved,
    )
    assert build_recommendation_reason(item) == "Recently saved and preserved."


def test_topics_and_recommendations_require_authentication(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch, login=False)

    topics_response = client.get("/api/topics/tree")
    recommendations_response = client.get("/api/recommendations")

    assert topics_response.status_code == 401
    assert recommendations_response.status_code == 401


def test_ai_endpoints_return_empty_lists_for_authenticated_user(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)

    topics_response = client.get("/api/topics/tree")
    recommendations_response = client.get("/api/recommendations")

    assert topics_response.status_code == 200
    assert topics_response.json() == {"topics": []}
    assert recommendations_response.status_code == 200
    assert recommendations_response.json() == {"items": []}


def test_ai_endpoints_publish_response_schemas(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)

    openapi = client.get("/openapi.json").json()
    topics_schema = openapi["paths"]["/api/topics/tree"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    recommendations_schema = openapi["paths"]["/api/recommendations"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]

    assert topics_schema == {"$ref": "#/components/schemas/TopicTreeResponse"}
    assert recommendations_schema == {"$ref": "#/components/schemas/RecommendationListResponse"}


def test_ai_endpoints_return_seeded_item_fields(tmp_path, monkeypatch):
    client, TestingSession = make_client(tmp_path, monkeypatch)
    saved_at = datetime(2026, 6, 14, tzinfo=timezone.utc)
    with TestingSession() as session:
        session.add(
            Item(
                id="item-ai",
                original_url="https://openai.com/research",
                normalized_url="https://openai.com/research",
                source_domain="openai.com",
                title="AI Research",
                description="Fallback summary",
                body_text=None,
                status=ItemStatus.preserved,
                saved_at=saved_at,
            )
        )
        session.commit()

    topics_response = client.get("/api/topics/tree")
    recommendations_response = client.get("/api/recommendations")

    assert topics_response.status_code == 200
    assert topics_response.json() == {
        "topics": [{"id": "ai", "name": "AI", "count": 1, "children": []}]
    }
    assert recommendations_response.status_code == 200
    assert recommendations_response.json() == {
        "items": [
            {
                "id": "item-ai",
                "title": "AI Research",
                "source_domain": "openai.com",
                "summary": "Fallback summary",
                "reason": "Recently saved and preserved.",
                "topic": "AI",
                "status": "preserved",
            }
        ]
    }


def test_recommendations_are_limited_to_twenty_and_ordered_newest_first(tmp_path, monkeypatch):
    client, TestingSession = make_client(tmp_path, monkeypatch)
    base_time = datetime(2026, 6, 14, tzinfo=timezone.utc)
    with TestingSession() as session:
        for index in range(25):
            session.add(
                Item(
                    id=f"item-{index:02d}",
                    original_url=f"https://example.com/{index}",
                    normalized_url=f"https://example.com/{index}",
                    source_domain="example.com",
                    title=f"Item {index:02d}",
                    status=ItemStatus.preserved,
                    saved_at=base_time + timedelta(minutes=index),
                )
            )
        session.commit()

    response = client.get("/api/recommendations")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 20
    assert [item["id"] for item in items] == [f"item-{index:02d}" for index in range(24, 4, -1)]
    assert items[0]["summary"] is None
