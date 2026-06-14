import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job, JobStatus, now_utc


def enqueue_job(
    db: Session,
    job_type: str,
    item_id: str | None = None,
    payload: dict[str, Any] | None = None,
    run_after: datetime | None = None,
) -> Job:
    job = Job(
        job_type=job_type,
        item_id=item_id,
        payload_json=json.dumps(payload or {}),
        run_after=run_after or now_utc(),
        status=JobStatus.queued,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def claim_next_job(db: Session) -> Job | None:
    job = db.scalar(
        select(Job)
        .where(Job.status == JobStatus.queued, Job.run_after <= now_utc())
        .order_by(Job.created_at)
        .limit(1)
    )
    if job is None:
        return None

    job.status = JobStatus.running
    job.attempts += 1
    job.updated_at = now_utc()
    db.commit()
    db.refresh(job)
    return job


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
