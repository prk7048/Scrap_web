import re

from app.db.models import Item


AI_KEYWORDS = {"ai", "llm", "model", "agent", "prompt", "openai"}
DEVELOPMENT_KEYWORDS = {"ubuntu", "windows", "docker", "python", "react"}


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def suggest_topic_name(item: Item) -> str:
    text = " ".join(filter(None, [item.title, item.body_text, item.source_domain]))
    tokens = _tokenize(text)
    source_domain = (item.source_domain or "").lower()
    if tokens & AI_KEYWORDS or source_domain == "ai" or source_domain.endswith(".ai"):
        return "AI"
    if tokens & DEVELOPMENT_KEYWORDS:
        return "Development"
    if "youtube" in tokens:
        return "YouTube"
    return "Unsorted"


def build_summary(item: Item) -> str | None:
    if item.body_text:
        return item.body_text[:280]
    return item.description


def build_recommendation_reason(item: Item) -> str:
    if item.status.value == "failed":
        return "Needs retry before it can be preserved."
    return "Recently saved and preserved."
