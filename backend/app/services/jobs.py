import json
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import Job, JobStatus, now_utc


def enqueue_job(
    db: Session,
    job_type: str,
    item_id: str | None = None,
    payload: dict[str, Any] | None = None,
    run_after: datetime | None = None,
    commit: bool = True,
) -> Job:
    job = Job(
        job_type=job_type,
        item_id=item_id,
        payload_json=json.dumps(payload or {}),
        run_after=run_after or now_utc(),
        status=JobStatus.queued,
    )
    db.add(job)
    if commit:
        db.commit()
        db.refresh(job)
    return job


def claim_next_job(db: Session) -> Job | None:
    while True:
        candidate_id = db.scalar(
            select(Job.id)
            .where(Job.status == JobStatus.queued, Job.run_after <= now_utc())
            .order_by(Job.created_at)
            .limit(1)
        )
        if candidate_id is None:
            return None

        result = db.execute(
            update(Job)
            .where(Job.id == candidate_id, Job.status == JobStatus.queued)
            .values(
                status=JobStatus.running,
                attempts=Job.attempts + 1,
                updated_at=now_utc(),
            )
        )
        if result.rowcount == 1:
            db.commit()
            return db.get(Job, candidate_id)

        db.rollback()


def complete_job(db: Session, job: Job) -> Job:
    job.status = JobStatus.complete
    job.error = None
    job.updated_at = now_utc()
    db.commit()
    db.refresh(job)
    return job


def fail_job(db: Session, job: Job, error: str) -> Job:
    job.status = JobStatus.failed
    job.error = error
    job.updated_at = now_utc()
    db.commit()
    db.refresh(job)
    return job
