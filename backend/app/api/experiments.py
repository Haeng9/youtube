"""실험(A/B) API (Story 4-1).

- GET  /api/experiments            입력(job)별로 묶은 실험 결과
- POST /api/experiments/run        한 입력 + step의 모든 provider를 A/B로 실행(백그라운드)
- GET  /api/experiments/{id}/result  실험 산출물 파일 서빙(경로 탈출 가드)
- PUT  /api/experiments/{id}/score   비교 점수 갱신
"""
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import config
from app.experiments.runner import run_experiment
from app.experiments.store import (
    get_experiment,
    list_experiments_grouped,
    set_score,
)
from app.jobs.queue import get_job
from app.pipeline.providers.loader import list_step_providers

router = APIRouter()

# 확장자 → media type 접두(미리보기 종류 결정). 그 외는 octet-stream.
_MEDIA_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".mp4": "video/mp4",
}


class RunRequest(BaseModel):
    job_id: str
    step: str
    params: dict | None = None
    # 비교할 provider를 지정(없으면 step의 모든 등록 provider). 깔끔한 A/B를 위해
    # 예: ["suno", "ace_step"] — 비활성 stub 등을 제외하고 둘만 비교.
    provider_names: list[str] | None = None


class ScoreRequest(BaseModel):
    score: int


@router.get("/experiments")
async def list_experiments():
    return {"groups": list_experiments_grouped()}


@router.post("/experiments/run", status_code=202)
async def run_experiments(req: RunRequest):
    job = get_job(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")

    candidates = [name for name, _ in list_step_providers(req.step)]
    if req.provider_names is not None:
        wanted = set(req.provider_names)
        candidates = [name for name in candidates if name in wanted]
    if not candidates:
        raise HTTPException(
            status_code=400, detail=f"'{req.step}' 단계에 비교할 provider가 없습니다."
        )

    # job에서 기본 입력 params 구성 후 요청 params로 병합 (config 동적 참조).
    params = {
        "input_path": str(config.UPLOAD_DIR / job.filename),
        "style": job.style,
    }
    if req.params:
        params.update(req.params)

    # 응답에 보고한 candidates와 스레드가 실제로 돌리는 집합을 일치시킨다(TOCTOU 회피):
    # 이미 해결된 candidates를 그대로 넘겨 재조회 시점차로 인한 불일치를 막는다.
    thread = threading.Thread(
        target=run_experiment,
        args=(req.job_id, req.step, params),
        kwargs={"provider_names": candidates},
        daemon=True,
    )
    thread.start()

    return {
        "job_id": req.job_id,
        "step": req.step,
        "candidates": candidates,
        "status": "started",
    }


@router.get("/experiments/{exp_id}/result")
async def get_result(exp_id: int):
    exp = get_experiment(exp_id)
    if not exp or not exp.result_path:
        raise HTTPException(status_code=404, detail="결과 파일이 없습니다.")

    file_path = Path(exp.result_path).resolve()
    # 진짜 경로 포함 검사 — str.startswith는 형제 디렉터리(outputs_evil 등 접두 공유)를
    # 통과시키므로 is_relative_to로 OUTPUT_DIR 하위인지 확인한다.
    if not file_path.is_relative_to(config.OUTPUT_DIR.resolve()):
        raise HTTPException(status_code=400, detail="잘못된 파일 경로입니다.")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

    media_type = _MEDIA_TYPES.get(file_path.suffix.lower(), "application/octet-stream")
    return FileResponse(path=str(file_path), media_type=media_type, filename=file_path.name)


@router.put("/experiments/{exp_id}/score")
async def update_score(exp_id: int, req: ScoreRequest):
    exp = set_score(exp_id, req.score)
    if exp is None:
        raise HTTPException(status_code=404, detail="실험을 찾을 수 없습니다.")
    return {"id": exp.id, "score": exp.score}
