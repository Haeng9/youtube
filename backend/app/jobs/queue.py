from enum import Enum
from typing import Optional
from sqlalchemy.exc import IntegrityError
from app.db import SessionLocal
from app.db.models import Job, User

DEFAULT_USER_ID = 1


def _ensure_default_user(db):
    """Phase 1 is single-user: make sure the hardcoded default user exists so the
    jobs.user_id foreign key is satisfied. Tolerates a concurrent insert race
    (two first-ever uploads) by rolling back the duplicate and continuing."""
    if db.get(User, DEFAULT_USER_ID) is not None:
        return
    try:
        db.add(User(id=DEFAULT_USER_ID))
        db.commit()
    except IntegrityError:
        db.rollback()  # another thread created it first — fine


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


def create_job(filename: str, style: str) -> Job:
    db = SessionLocal()
    try:
        _ensure_default_user(db)
        job = Job(filename=filename, style=style, user_id=DEFAULT_USER_ID, status=JobStatus.PENDING, message="대기 중...")
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_job(job_id: str) -> Optional[Job]:
    db = SessionLocal()
    try:
        return db.get(Job, job_id)
    finally:
        db.close()


def update_job(job_id: str, status: JobStatus, message: str, output_file: str = None):
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job:
            job.status = status
            job.message = message
            if output_file:
                job.output_file = output_file
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
