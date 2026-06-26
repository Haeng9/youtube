"""SDXL 기반 로컬 커버 이미지 생성 provider (Story 3-1).

프롬프트(+선택 negative_prompt/size)로 커버 이미지를 로컬에서 생성해
data/outputs/{job_id}/image/cover.png 에 저장한다. image stub을 대체(활성 전환)한다.

diffusers 파이프라인 로딩은 _load_pipeline()으로 분리한다(의존성 seam). SDXL 가중치는
~7GB라 테스트에서 실모델을 띄울 수 없으므로, 테스트는 이 함수를 가벼운 대역으로 monkeypatch해
파라미터 매핑/저장/반환 로직을 실제로 검증한다(목 금지 컨벤션). diffusers 미설치 등
로딩 실패는 예외를 밖으로 던지지 않고 graceful 실패(ProviderResult)로 변환한다.
"""
from app import config
from app.pipeline.providers.base import BaseImageProvider, ProviderResult

# SDXL 1.0 base — OpenRAIL++-M(상업 허용), 1024² 네이티브. 가중치는 MODELS_DIR/sdxl로 다운로드.
MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"

# size 미지정/형식 불일치 시 기본 해상도(SDXL 네이티브).
DEFAULT_SIZE = (1024, 1024)


def _parse_size(size):
    """size를 (width, height)로 정규화. [w, h] 형태만 수용하고, 없거나 형식이 다르면
    기본 1024×1024. SDXL은 8(이상적으로 64) 배수 해상도를 기대하나 검증은 호출 라이브러리에 위임.
    길이 2여도 원소가 정수로 변환되지 않으면(예: ["1024", "bad"]) 형식 불일치로 보고 기본값."""
    if isinstance(size, (list, tuple)) and len(size) == 2:
        try:
            return int(size[0]), int(size[1])
        except (TypeError, ValueError):
            return DEFAULT_SIZE
    return DEFAULT_SIZE


def _first_image(output):
    """diffusers 파이프라인 호출 결과에서 첫 이미지를 고른다. 표준 출력은 `.images` 리스트.
    리스트/튜플을 직접 돌려주는 대역도 수용한다. 비면 None."""
    images = getattr(output, "images", None)
    if images is None and isinstance(output, (list, tuple)):
        images = output
    if not images:
        return None
    return images[0]


def _load_pipeline():
    """SDXL 파이프라인을 로드해 반환. device/dtype 자동선택 — CUDA면 fp16(+fp16 variant)로
    적재해 GPU로, 없으면 fp32 CPU. 가중치는 HF cache_dir=MODELS_DIR/sdxl로 다운로드(git 제외).
    미설치/로드 실패 시 예외를 그대로 올리며, 호출부(run)가 graceful 실패로 변환한다."""
    import torch
    from diffusers import StableDiffusionXLPipeline

    cache_dir = str(config.MODELS_DIR / "sdxl")
    if torch.cuda.is_available():
        pipeline = StableDiffusionXLPipeline.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.float16,
            variant="fp16",
            use_safetensors=True,
            cache_dir=cache_dir,
        )
        pipeline = pipeline.to("cuda")
    else:
        pipeline = StableDiffusionXLPipeline.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.float32,
            use_safetensors=True,
            cache_dir=cache_dir,
        )
    return pipeline


class SdxlProvider(BaseImageProvider):
    async def run(self, job_id, params) -> ProviderResult:
        try:
            pipeline = _load_pipeline()
        except Exception as e:
            return ProviderResult(
                success=False,
                error=f"diffusers/SDXL 미설치 또는 로드 실패 — {type(e).__name__}: {e}",
            )
        if pipeline is None:
            return ProviderResult(
                success=False, error="SDXL 파이프라인 로드 실패 (None 반환)"
            )

        try:
            prompt = (
                params.get("prompt")
                or params.get("style_prompt")
                or params.get("style")
                or ""
            )
            negative_prompt = params.get("negative_prompt") or ""
            width, height = _parse_size(params.get("size"))

            image_dir = config.OUTPUT_DIR / str(job_id) / "image"
            image_dir.mkdir(parents=True, exist_ok=True)
            out_path = image_dir / "cover.png"

            output = pipeline(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
            )

            image = _first_image(output)
            if image is None:
                return ProviderResult(
                    success=False, error="SDXL가 이미지를 반환하지 않음"
                )
            image.save(str(out_path))

            return ProviderResult(
                success=True,
                output_path=str(out_path),
                metadata={
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "size": [width, height],
                },
            )
        except Exception as e:
            return ProviderResult(success=False, error=f"{type(e).__name__}: {e}")
