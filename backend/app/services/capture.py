from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from readability import Document
from sqlalchemy.orm import Session

from app.db.models import Artifact, ArtifactType, Item, ItemStatus


@dataclass(frozen=True)
class CaptureResult:
    title: str | None
    description: str | None
    body_text: str | None
    html: str | None
    screenshot_bytes: bytes | None
    failure_reason: str | None = None


def item_artifact_dir(data_dir: Path, item: Item) -> Path:
    try:
        item_id = str(UUID(item.id))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid item id for artifact path") from exc

    base_dir = data_dir.resolve()
    path = (base_dir / "items" / item_id).resolve()
    if not path.is_relative_to(base_dir):
        raise ValueError("Artifact path escapes data directory")
    path.mkdir(parents=True, exist_ok=True)
    return path


def store_capture_result(
    db: Session,
    item: Item,
    data_dir: Path,
    title: str | None,
    description: str | None,
    body_text: str | None,
    html: str | None,
    screenshot_bytes: bytes | None,
    failure_reason: str | None = None,
) -> None:
    base_dir = data_dir.resolve()
    artifact_dir = item_artifact_dir(base_dir, item)
    item.title = title
    item.description = description
    item.body_text = body_text
    item.status = ItemStatus.classification_needed if failure_reason else ItemStatus.preserved
    item.failure_reason = failure_reason

    if html:
        html_path = artifact_dir / "snapshot.html"
        html_path.write_text(html, encoding="utf-8")
        db.add(
            Artifact(
                item_id=item.id,
                artifact_type=ArtifactType.html,
                path=str(html_path.relative_to(base_dir)),
                mime_type="text/html",
            )
        )

    if screenshot_bytes:
        screenshot_path = artifact_dir / "screenshot.png"
        screenshot_path.write_bytes(screenshot_bytes)
        db.add(
            Artifact(
                item_id=item.id,
                artifact_type=ArtifactType.screenshot,
                path=str(screenshot_path.relative_to(base_dir)),
                mime_type="image/png",
            )
        )
    db.commit()
    db.refresh(item)


def extract_text(html: str) -> tuple[str | None, str | None, str]:
    document = Document(html)
    title = document.short_title()
    summary_html = document.summary()
    soup = BeautifulSoup(summary_html, "html.parser")
    body_text = soup.get_text("\n", strip=True)
    description_node = BeautifulSoup(html, "html.parser").find("meta", attrs={"name": "description"})
    description = description_node.get("content") if description_node else None
    return title, description, body_text


async def capture_url(url: str, timeout_ms: int) -> CaptureResult:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            html = await page.content()
            title, description, body_text = extract_text(html)
            screenshot_bytes = None
            failure_reason = None
            try:
                screenshot_bytes = await page.screenshot(full_page=True)
            except Exception as exc:
                failure_reason = str(exc)
        finally:
            await browser.close()
    return CaptureResult(
        title=title,
        description=description,
        body_text=body_text,
        html=html,
        screenshot_bytes=screenshot_bytes,
        failure_reason=failure_reason,
    )
