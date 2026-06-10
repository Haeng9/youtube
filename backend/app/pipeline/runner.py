from app.jobs.queue import update_job, JobStatus


def run_pipeline(job_id: str, input_path: str, style: str):
    """
    AI 파이프라인 실행 순서:
    1. Demucs      - 보컬/반주 분리
    2. RVC         - 보컬 스타일 변환
    3. MusicGen    - 반주 재생성
    4. SD          - 커버 이미지 생성
    5. FFmpeg      - 최종 영상 합성
    """
    try:
        update_job(job_id, JobStatus.PROCESSING, "파이프라인 시작...")

        # TODO: Step 1 - Demucs 보컬/반주 분리
        update_job(job_id, JobStatus.PROCESSING, "[1/5] 보컬 분리 중...")
        # from app.pipeline.demucs_step import separate
        # vocal_path, bgm_path = separate(input_path)

        # TODO: Step 2 - RVC 보컬 스타일 변환
        update_job(job_id, JobStatus.PROCESSING, "[2/5] 보컬 스타일 변환 중...")
        # from app.pipeline.rvc_step import convert
        # converted_vocal = convert(vocal_path, style)

        # TODO: Step 3 - MusicGen 반주 재생성
        update_job(job_id, JobStatus.PROCESSING, "[3/5] 반주 생성 중...")
        # from app.pipeline.musicgen_step import generate_bgm
        # new_bgm = generate_bgm(bgm_path, style)

        # TODO: Step 4 - Stable Diffusion 커버 이미지 생성
        update_job(job_id, JobStatus.PROCESSING, "[4/5] 커버 이미지 생성 중...")
        # from app.pipeline.sd_step import generate_image
        # image_path = generate_image(style)

        # TODO: Step 5 - FFmpeg 최종 영상 합성
        update_job(job_id, JobStatus.PROCESSING, "[5/5] 영상 합성 중...")
        # from app.pipeline.ffmpeg_step import render
        # output_file = render(converted_vocal, new_bgm, image_path)

        update_job(job_id, JobStatus.FAILED, "파이프라인 스텝 미구현 (TODO)")

    except Exception as e:
        update_job(job_id, JobStatus.FAILED, f"오류: {str(e)}")
