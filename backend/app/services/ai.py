from app.db.models import Item


def suggest_topic_name(item: Item) -> str:
    text = " ".join(filter(None, [item.title, item.body_text, item.source_domain])).lower()
    if any(keyword in text for keyword in ["ai", "llm", "model", "agent", "prompt"]):
        return "AI"
    if any(keyword in text for keyword in ["ubuntu", "windows", "docker", "python", "react"]):
        return "Development"
    if "youtube" in text:
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
