from app.db.models import Item, ItemStatus
from app.services.ai import build_recommendation_reason, suggest_topic_name


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


def test_recommendation_reason_mentions_recent_saved_item():
    item = Item(
        original_url="https://example.com",
        normalized_url="https://example.com",
        source_domain="example.com",
        title="Example",
        status=ItemStatus.preserved,
    )
    assert build_recommendation_reason(item) == "Recently saved and preserved."
