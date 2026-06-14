import asyncio
from pathlib import Path
from time import sleep

from app.core.config import get_settings
from app.db.models import Item, ItemStatus
from app.db.session import SessionLocal
from app.services.capture import capture_url, store_capture_result
from app.services.jobs import claim_next_job, complete_job, fail_job


async def process_capture_item(item_id: str) -> None:
    settings = get_settings()
    with SessionLocal() as db:
        item = db.get(Item, item_id)
        if item is None:
            return
        item.status = ItemStatus.processing
        db.commit()
        try:
            title, description, body_text, html, screenshot = await capture_url(
                item.normalized_url,
                settings.capture_timeout_ms,
            )
            store_capture_result(db, item, Path(settings.data_dir), title, description, body_text, html, screenshot)
        except Exception as exc:
            db.rollback()
            failed_item = db.get(Item, item_id)
            if failed_item is not None:
                failed_item.status = ItemStatus.failed
                failed_item.failure_reason = str(exc)
                db.commit()
            raise


async def run_once() -> bool:
    with SessionLocal() as db:
        job = claim_next_job(db)
        if job is None:
            return False
        job_id = job.id
        try:
            if job.job_type != "capture_item":
                raise ValueError(f"Unsupported job type: {job.job_type}")
            if not job.item_id:
                raise ValueError("capture_item job missing item_id")
            await process_capture_item(job.item_id)
            complete_job(db, job)
        except Exception as exc:
            db.rollback()
            failed_job = db.get(type(job), job_id)
            if failed_job is not None:
                fail_job(db, failed_job, str(exc))
    return True


def main() -> None:
    while True:
        did_work = asyncio.run(run_once())
        if not did_work:
            sleep(2)


if __name__ == "__main__":
    main()
