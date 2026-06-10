from fastapi import APIRouter, HTTPException
from app.jobs.queue import get_job

router = APIRouter()


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    return {
        "job_id": job.job_id,
        "status": job.status,
        "message": job.message,
        "output_file": job.output_file,
    }
