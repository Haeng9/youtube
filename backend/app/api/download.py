from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from app.jobs.queue import get_job
from app.config import OUTPUT_DIR

router = APIRouter()


@router.get("/download/{job_id}")
async def download_result(job_id: str):
    job = get_job(job_id)
    if not job or not job.output_file:
        raise HTTPException(status_code=404, detail="결과 파일이 없습니다.")

    file_path = (OUTPUT_DIR / job.output_file).resolve()
    if not str(file_path).startswith(str(OUTPUT_DIR.resolve())):
        raise HTTPException(status_code=400, detail="잘못된 파일 경로입니다.")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

    return FileResponse(path=str(file_path), media_type="video/mp4", filename=job.output_file)
