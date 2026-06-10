"""Demucs 기반 음원 분리 provider (Story 1-4).

업로드된 MP3를 htdemucs(4-stem) 모델로 분리해 vocals.wav + no_vocals.wav를
data/outputs/{job_id}/stems/ 에 저장한다. separation stub을 대체한다.

WAV 저장은 표준 라이브러리 wave로 직접 수행한다. demucs.api.save_audio는 .wav 저장 시
torchaudio.save를 호출하는데, torchaudio 2.9+는 이를 torchcodec 백엔드에 위임하고
torchcodec은 Windows에서 FFmpeg 공유 DLL을 요구해 로딩이 불안정하다. 분리(AC3 핵심)는
demucs.api.Separator를 그대로 사용하며, 저장만 백엔드 비의존적 방식으로 처리한다.
"""
import wave

import torch
from demucs.api import Separator

from app.config import OUTPUT_DIR
from app.pipeline.providers.base import BaseSeparationProvider, ProviderResult


def _save_wav(tensor: torch.Tensor, path, samplerate: int) -> None:
    """(channels, samples) float[-1,1] 텐서를 16-bit PCM WAV로 저장."""
    wav = tensor.detach().cpu().clamp(-1.0, 1.0)
    int16 = (wav * 32767.0).to(torch.int16)  # (channels, samples)
    channels = int16.shape[0]
    interleaved = int16.t().contiguous().view(-1).numpy().tobytes()
    with wave.open(str(path), "w") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(samplerate)
        w.writeframes(interleaved)


class DemucsProvider(BaseSeparationProvider):
    async def run(self, job_id, params) -> ProviderResult:
        try:
            input_path = params["input_path"]

            stems_dir = OUTPUT_DIR / str(job_id) / "stems"
            stems_dir.mkdir(parents=True, exist_ok=True)
            vocals_path = stems_dir / "vocals.wav"
            no_vocals_path = stems_dir / "no_vocals.wav"

            # device 자동 선택 (CUDA 있으면 GPU, 없으면 CPU) — 하드코딩 금지 (AC5)
            device = "cuda" if torch.cuda.is_available() else "cpu"
            separator = Separator(model="htdemucs", device=device)

            _origin, stems = separator.separate_audio_file(input_path)

            # htdemucs는 native "no_vocals"가 없으므로 나머지 stem 합으로 구성 (AC4)
            no_vocals = stems["drums"] + stems["bass"] + stems["other"]

            _save_wav(stems["vocals"], vocals_path, separator.samplerate)
            _save_wav(no_vocals, no_vocals_path, separator.samplerate)

            return ProviderResult(
                success=True,
                output_path=str(no_vocals_path),
                metadata={
                    "vocals": str(vocals_path),
                    "no_vocals": str(no_vocals_path),
                },
            )
        except Exception as e:
            return ProviderResult(success=False, error=f"{type(e).__name__}: {e}")
