import threading
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.config import UPLOAD_DIR
from app.jobs.queue import create_job
from app.pipeline.runner import run_pipeline

router = APIRouter()

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    style: str = Form(...),
):
    if not file.filename or not file.filename.endswith(".mp3"):
        raise HTTPException(status_code=400, detail="MP3 파일만 업로드 가능합니다.")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="파일이 너무 큽니다. (최대 50MB)")

    # Strip any path components and prefix with UUID to prevent traversal and collisions
    safe_name = Path(file.filename).name
    unique_filename = f"{uuid.uuid4().hex}_{safe_name}"
    save_path = UPLOAD_DIR / unique_filename
    save_path.write_bytes(content)

    job = create_job(filename=unique_filename, style=style)

    thread = threading.Thread(
        target=run_pipeline, args=(job.job_id, str(save_path), style)
    )
    thread.daemon = True
    thread.start()

    return {"job_id": job.job_id}
