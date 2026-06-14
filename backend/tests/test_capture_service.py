from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import Artifact, ArtifactType, Base, Item, ItemStatus
from app.services.capture import store_capture_result


def test_store_capture_result_writes_artifacts(tmp_path: Path):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        item = Item(
            original_url="https://example.com",
            normalized_url="https://example.com",
            source_domain="example.com",
        )
        session.add(item)
        session.commit()
        session.refresh(item)

        store_capture_result(
            session,
            item,
            data_dir=tmp_path,
            title="Example",
            description="A page",
            body_text="Readable body",
            html="<html><body>Readable body</body></html>",
            screenshot_bytes=b"fake-png",
        )

        artifacts = session.scalars(select(Artifact).where(Artifact.item_id == item.id)).all()

    assert item.status == ItemStatus.preserved
    assert item.title == "Example"
    assert item.body_text == "Readable body"
    assert {artifact.artifact_type for artifact in artifacts} == {ArtifactType.html, ArtifactType.screenshot}
    assert all((tmp_path / artifact.path).exists() for artifact in artifacts)
