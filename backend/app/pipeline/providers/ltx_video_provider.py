"""LTX-Video 기반 로컬 i2v(image-to-video) 영상 생성 provider (Story 3-2).

image 단계 산출물(cover.png)을 입력으로 받아 짧은 MP4 클립을 로컬에서 생성해
data/outputs/{job_id}/video/clip.mp4 에 저장한다. video stub을 대체(활성 전환)한다.

diffusers 파이프라인 로딩(_load_pipeline)과 영상 export(_export_video)를 모듈 레벨
함수로 분리한다(의존성 seam 2개). LTX 가중치는 수 GB라 테스트에서 실모델을 못 띄우므로,
테스트는 이 두 함수를 가벼운 대역으로 monkeypatch해 우리 오케스트레이션(이미지 로드/파라미터
매핑/프레임 추출/저장/반환)을 실제 코드로 검증한다(목 금지 컨벤션). diffusers/LTX/export
백엔드 미설치 등 로딩 실패는 예외를 밖으로 던지지 않고 graceful 실패(ProviderResult)로 변환한다.

모델 = LTX-Video (Lightricks). 연 매출 $10M 미만은 상업적 사용 무료(OpenRAIL 기반).
RTX 3060 12GB는 실용 베이스라인 — bf16 + enable_model_cpu_offload + 보수 해상도/프레임으로 적재.
"""
from app import config
from app.pipeline.providers.base import BaseVideoProvider, ProviderResult

# LTX-Video — diffusers LTXImageToVideoPipeline. 가중치는 MODELS_DIR/ltx-video로 다운로드.
MODEL_ID = "Lightricks/LTX-Video"

# size 미지정/형식 불일치 시 기본 해상도. 12GB 친화 보수값(16:9, 둘 다 32 배수).
DEFAULT_SIZE = (512, 288)

# duration 미지정 시 기본 클립 길이(초)와 프레임레이트. num_frames는 8k+1 형태로 정규화.
DEFAULT_DURATION_SECONDS = 2
DEFAULT_FPS = 24


def _parse_size(size):
    """size를 (width, height)로 정규화. [w, h] 형태만 수용하고, 없거나 형식이 다르면 기본값.
    길이 2여도 원소가 정수로 변환되지 않으면(예: ["512","bad"]) 형식 불일치로 보고 기본값.
    LTX는 32 배수 width/height를 기대하나 검증은 호출 라이브러리에 위임(3-1 _parse_size 계약)."""
    if isinstance(size, (list, tuple)) and len(size) == 2:
        try:
            return int(size[0]), int(size[1])
        except (TypeError, ValueError):
            return DEFAULT_SIZE
    return DEFAULT_SIZE


def _resolve_num_frames(duration_seconds, fps):
    """duration(초)·fps로 num_frames를 계산하고 LTX가 기대하는 8k+1 형태로 올림 정규화.
    duration이 없거나 정수로 변환 불가하면 기본값을 쓴다. 최소 9프레임 보장."""
    try:
        seconds = float(duration_seconds)
        if seconds <= 0:
            seconds = DEFAULT_DURATION_SECONDS
    except (TypeError, ValueError):
        seconds = DEFAULT_DURATION_SECONDS
    raw = max(int(round(seconds * fps)), 8)
    # 8의 배수 + 1 (예: 49, 57, ...). raw 이상으로 올림.
    return ((raw + 7) // 8) * 8 + 1


def _frames_from_output(output):
    """diffusers LTX 파이프라인 결과에서 첫 비디오의 프레임 리스트를 고른다. 표준 출력은
    `.frames`(= List[List[PIL.Image]])이고 frames[0]이 첫 비디오. 리스트/튜플 직접 반환도
    수용한다. 비면 None."""
    frames = getattr(output, "frames", None)
    if frames is None and isinstance(output, (list, tuple)):
        frames = output
    if not frames:
        return None
    return frames[0]


def _load_pipeline():
    """LTX-Video i2v 파이프라인을 로드해 반환. device/dtype 자동선택 — CUDA면 bf16으로 적재 후
    enable_model_cpu_offload()로 12GB VRAM을 절약(.to('cuda') 대신), 없으면 fp32 CPU.
    가중치는 HF cache_dir=MODELS_DIR/ltx-video로 다운로드(git 제외). 미설치/로드 실패 시 예외를
    그대로 올리며, 호출부(run)가 graceful 실패로 변환한다."""
    import torch
    from diffusers import LTXImageToVideoPipeline

    cache_dir = str(config.MODELS_DIR / "ltx-video")
    if torch.cuda.is_available():
        pipeline = LTXImageToVideoPipeline.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.bfloat16,
            cache_dir=cache_dir,
        )
        # 12GB에 적재하기 위해 .to('cuda') 대신 CPU offload (느리지만 VRAM 절약).
        pipeline.enable_model_cpu_offload()
    else:
        pipeline = LTXImageToVideoPipeline.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.float32,
            cache_dir=cache_dir,
        )
    return pipeline


def _export_video(frames, path, fps):
    """프레임(PIL 이미지) 시퀀스를 MP4로 저장. diffusers export_to_video(imageio-ffmpeg 백엔드)
    사용. 백엔드 미설치 시 예외를 그대로 올리며 호출부(run)가 graceful 실패로 변환한다."""
    from diffusers.utils import export_to_video

    export_to_video(frames, str(path), fps=fps)


def _load_image(image_path):
    """입력 이미지(cover.png)를 PIL RGB로 로드. 호출부에서 경로 유효성은 이미 확인."""
    from PIL import Image

    return Image.open(str(image_path)).convert("RGB")


class LtxVideoProvider(BaseVideoProvider):
    async def run(self, job_id, params) -> ProviderResult:
        # i2v 입력 이미지 경로 — image step 산출물(cover.png). 없으면 진행 불가.
        image_path = params.get("image_path") or params.get("image_output")
        if not image_path:
            return ProviderResult(
                success=False,
                error="video 단계 입력 이미지(image_path)가 없습니다 — image 단계 산출물 필요",
            )

        try:
            pipeline = _load_pipeline()
        except Exception as e:
            return ProviderResult(
                success=False,
                error=f"diffusers/LTX-Video 미설치 또는 로드 실패 — {type(e).__name__}: {e}",
            )
        if pipeline is None:
            return ProviderResult(
                success=False, error="LTX-Video 파이프라인 로드 실패 (None 반환)"
            )

        try:
            image = _load_image(image_path)

            prompt = (
                params.get("prompt")
                or params.get("style_prompt")
                or params.get("style")
                or ""
            )
            negative_prompt = params.get("negative_prompt") or ""
            width, height = _parse_size(params.get("size"))
            fps = DEFAULT_FPS
            num_frames = _resolve_num_frames(params.get("duration_seconds"), fps)

            video_dir = config.OUTPUT_DIR / str(job_id) / "video"
            video_dir.mkdir(parents=True, exist_ok=True)
            out_path = video_dir / "clip.mp4"

            output = pipeline(
                image=image,
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                num_frames=num_frames,
                frame_rate=fps,
            )

            frames = _frames_from_output(output)
            if frames is None:
                return ProviderResult(
                    success=False, error="LTX-Video가 프레임을 반환하지 않음"
                )

            _export_video(frames, out_path, fps)

            return ProviderResult(
                success=True,
                output_path=str(out_path),
                metadata={
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "size": [width, height],
                    "num_frames": num_frames,
                    "fps": fps,
                    "image_path": str(image_path),
                },
            )
        except Exception as e:
            return ProviderResult(success=False, error=f"{type(e).__name__}: {e}")
