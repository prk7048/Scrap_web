from pathlib import Path

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from readability import Document
from sqlalchemy.orm import Session

from app.db.models import Artifact, ArtifactType, Item, ItemStatus


def item_artifact_dir(data_dir: Path, item: Item) -> Path:
    path = data_dir / "items" / item.id
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
) -> None:
    artifact_dir = item_artifact_dir(data_dir, item)
    item.title = title
    item.description = description
    item.body_text = body_text
    item.status = ItemStatus.preserved
    item.failure_reason = None

    if html:
        html_path = artifact_dir / "snapshot.html"
        html_path.write_text(html, encoding="utf-8")
        db.add(
            Artifact(
                item_id=item.id,
                artifact_type=ArtifactType.html,
                path=str(html_path.relative_to(data_dir)),
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
                path=str(screenshot_path.relative_to(data_dir)),
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


async def capture_url(url: str, timeout_ms: int) -> tuple[str | None, str | None, str | None, str | None, bytes | None]:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            html = await page.content()
            screenshot_bytes = await page.screenshot(full_page=True)
        finally:
            await browser.close()
    title, description, body_text = extract_text(html)
    return title, description, body_text, html, screenshot_bytes
