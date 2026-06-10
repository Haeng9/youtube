import uuid
from enum import Enum
from typing import Dict, Optional


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class Job:
    def __init__(self, job_id: str, filename: str, style: str):
        self.job_id = job_id
        self.filename = filename
        self.style = style
        self.status = JobStatus.PENDING
        self.message = "대기 중..."
        self.output_file: Optional[str] = None


# Phase 1: 인메모리 (Phase 2에서 Redis/DB로 교체)
_jobs: Dict[str, Job] = {}


def create_job(filename: str, style: str) -> Job:
    job_id = str(uuid.uuid4())
    job = Job(job_id, filename, style)
    _jobs[job_id] = job
    return job


def get_job(job_id: str) -> Optional[Job]:
    return _jobs.get(job_id)


def update_job(job_id: str, status: JobStatus, message: str, output_file: str = None):
    job = _jobs.get(job_id)
    if job:
        job.status = status
        job.message = message
        if output_file:
            job.output_file = output_file
