import asyncio

from app.jobs.queue import update_job, JobStatus
from app.pipeline.providers.loader import get_active_provider

# 파이프라인 단계 순서: (DB step, 진행 메시지)
PIPELINE_STEPS = [
    ("separation", "[1/5] 보컬 분리 중..."),
    ("music", "[2/5] 음악 생성 중..."),
    ("image", "[3/5] 커버 이미지 생성 중..."),
    ("video", "[4/5] 영상 생성 중..."),
    ("synthesis", "[5/5] 최종 영상 합성 중..."),
]


def run_pipeline(job_id: str, input_path: str, style: str):
    """DB에 설정된 provider를 단계별로 로딩해 실행한다.
    현재는 stub provider라 실제 출력 파일은 생성되지 않는다."""
    try:
        update_job(job_id, JobStatus.PROCESSING, "파이프라인 시작...")

        params = {"input_path": input_path, "style": style}

        for step, message in PIPELINE_STEPS:
            update_job(job_id, JobStatus.PROCESSING, message)

            provider = get_active_provider(step)
            if provider is None:
                update_job(job_id, JobStatus.FAILED, f"'{step}' 단계의 활성 provider가 없습니다.")
                return

            result = asyncio.run(provider.run(job_id, params))
            if not result.success:
                update_job(job_id, JobStatus.FAILED, f"'{step}' 단계 실패: {result.error}")
                return

            # 이 step의 출력을 다음 step params로 누적 전달 (AC9).
            # separation 출력(no_vocals.wav = MR)이 music step의 reference_audio_path가 된다.
            if result.output_path:
                params[f"{step}_output"] = result.output_path
                if step == "separation":
                    params["reference_audio_path"] = result.output_path
                # image 산출물(cover.png)을 video step의 i2v 입력 + synthesis의 커버로 연결.
                if step == "image":
                    params["image_path"] = result.output_path
                    params["cover_image_path"] = result.output_path
                # music 산출물을 synthesis의 오디오로 연결 (음악+영상+커버 → output.mp4).
                if step == "music":
                    params["audio_path"] = result.output_path
            params.update(result.metadata or {})

        update_job(job_id, JobStatus.DONE, "파이프라인 완료")

    except Exception as e:
        update_job(job_id, JobStatus.FAILED, f"오류: {str(e)}")
