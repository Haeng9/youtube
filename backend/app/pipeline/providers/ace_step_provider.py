"""ACE-Step 기반 로컬 원곡 음악 생성 provider (Story 2-2).

스타일 프롬프트(+선택 가사/길이)로 오리지널 음악을 로컬에서 생성해
data/outputs/{job_id}/music/ 에 저장한다. Suno(커버)와 공존하며, A/B 비교는 Story 4.1.
이 provider는 DB에 is_active=False로 등록되어 기본 파이프라인 흐름에서는 선택되지 않는다.

ACE-Step 파이프라인 로딩은 _load_pipeline()으로 분리한다(의존성 seam). 무거운 모델이라
테스트에서 실모델을 띄울 수 없으므로, 테스트는 이 함수를 가벼운 대역으로 monkeypatch해
파라미터 매핑/저장/반환 로직을 실제로 검증한다(목 금지 컨벤션). ace-step 미설치 등
로딩 실패는 예외를 밖으로 던지지 않고 graceful 실패(ProviderResult)로 변환한다.
"""
from app import config
from app.pipeline.providers.base import BaseMusicProvider, ProviderResult

# params에 duration이 없을 때 기본 생성 길이(초). 짧을수록 빠름.
DEFAULT_DURATION_SECONDS = 30.0


def _save_wav_file(target_wav, idx, save_path=None, sample_rate=48000, format="wav"):
    """ACE-Step의 save_wav_file 대체 — soundfile로 직접 저장한다.
    원본은 torchaudio.save를 쓰는데 torchaudio 2.9+는 저장을 torchcodec에 위임하고
    torchcodec은 Windows에서 불안정/미설치라 ImportError가 난다(Demucs 1-4와 동일 이슈).
    self 없이 인스턴스 속성으로 바인딩되므로 첫 인자는 self가 아니라 target_wav다.
    target_wav: (channels, samples) float 텐서 → soundfile은 (frames, channels)를 받으므로 전치."""
    import os
    import time

    import soundfile as sf

    if save_path is None:
        base = "./outputs"
        os.makedirs(base, exist_ok=True)
        out_path = f"{base}/output_{time.strftime('%Y%m%d%H%M%S')}_{idx}.{format}"
    elif os.path.isdir(save_path):
        out_path = os.path.join(
            save_path, f"output_{time.strftime('%Y%m%d%H%M%S')}_{idx}.{format}"
        )
    else:
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        out_path = save_path

    data = target_wav.detach().cpu().float().numpy().T  # (channels, samples) → (samples, channels)
    sf.write(out_path, data, sample_rate, format=format.upper())
    return out_path


def _load_pipeline():
    """ACE-Step 파이프라인을 로드해 반환. device는 자동 선택(CUDA 있으면 GPU, 없으면 CPU).
    저장은 torchcodec 우회를 위해 soundfile 기반(_save_wav_file)으로 교체한다.
    미설치/로드 실패 시 예외를 그대로 올리며, 호출부(run)가 graceful 실패로 변환한다."""
    import torch
    from acestep.pipeline_ace_step import ACEStepPipeline

    checkpoint_dir = str(config.MODELS_DIR / "ace-step")
    dtype = "bfloat16" if torch.cuda.is_available() else "float32"
    pipeline = ACEStepPipeline(checkpoint_dir=checkpoint_dir, dtype=dtype)
    # torchaudio.save → torchcodec 의존을 피하려 인스턴스의 저장 메서드를 교체(self 비바인딩).
    pipeline.save_wav_file = _save_wav_file
    return pipeline


def _first_audio_path(outputs):
    """ACE-Step __call__은 [생성 오디오 경로들..., 입력 파라미터 dict]를 반환한다.
    첫 번째 문자열(경로) 요소를 고른다. dict 등 비경로는 건너뛴다."""
    if not outputs:
        return None
    for item in outputs:
        if isinstance(item, str):
            return item
    return None


class AceStepProvider(BaseMusicProvider):
    async def run(self, job_id, params) -> ProviderResult:
        try:
            pipeline = _load_pipeline()
        except Exception as e:
            return ProviderResult(
                success=False,
                error=f"ace-step 미설치 또는 로드 실패 — {type(e).__name__}: {e}",
            )
        if pipeline is None:
            return ProviderResult(
                success=False, error="ace-step 파이프라인 로드 실패 (None 반환)"
            )

        try:
            style_prompt = params.get("style_prompt") or params.get("style") or ""
            duration = float(params.get("duration_seconds") or DEFAULT_DURATION_SECONDS)
            # ACE-Step __call__은 lyrics에 len()을 호출한다 → None이면 TypeError.
            # 가사가 없으면 빈 문자열(=instrumental)을 넘긴다.
            lyrics = params.get("lyrics") or ""

            music_dir = config.OUTPUT_DIR / str(job_id) / "music"
            music_dir.mkdir(parents=True, exist_ok=True)
            save_path = music_dir / "ace_step.wav"

            outputs = pipeline(
                format="wav",
                audio_duration=duration,
                prompt=style_prompt,
                lyrics=lyrics,
                save_path=str(save_path),
            )

            audio_path = _first_audio_path(outputs)
            if not audio_path:
                return ProviderResult(
                    success=False, error="ACE-Step가 오디오 경로를 반환하지 않음"
                )

            return ProviderResult(
                success=True,
                output_path=str(audio_path),
                metadata={
                    "prompt": style_prompt,
                    "audio_duration": duration,
                    "lyrics": lyrics,
                },
            )
        except Exception as e:
            return ProviderResult(success=False, error=f"{type(e).__name__}: {e}")
