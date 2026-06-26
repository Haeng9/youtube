"""AceStepProvider 테스트 (Story 2-2).

목 금지 — ACE-Step 실모델은 수 GB라 테스트에서 못 띄운다(보류 결정 2). 대신 외부 파이프라인
의존성을 가벼운 대역(stand-in)으로 주입(seam)해 우리 오케스트레이션 로직(파라미터 매핑/
출력 경로/저장/graceful 실패)을 실제 코드로 검증한다. 실 ACE-Step 생성은 별도 smoke로 보류.
"""
import asyncio
import wave
from pathlib import Path

from app import config
from app.pipeline.providers import ace_step_provider
from app.pipeline.providers.ace_step_provider import AceStepProvider
from app.pipeline.providers.base import BaseMusicProvider


def _write_tiny_wav(path):
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 100)


class _StandInPipeline:
    """ACE-Step 파이프라인의 가벼운 대역 — 받은 kwargs를 기록하고 save_path에 작은 wav를 쓴 뒤
    실제 ACE-Step과 동일하게 [오디오 경로, 입력 파라미터 dict]를 반환한다."""

    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        save_path = kwargs["save_path"]
        _write_tiny_wav(save_path)
        return [save_path, dict(kwargs)]


def test_ace_step_is_music_provider():
    assert isinstance(AceStepProvider(), BaseMusicProvider)


def test_unavailable_pipeline_importerror_fails_gracefully(monkeypatch):
    # ace-step 미설치(ImportError) 시 예외를 던지지 않고 success=False로 떨어져야 한다 (AC6).
    def _raise():
        raise ImportError("No module named 'acestep'")

    monkeypatch.setattr(ace_step_provider, "_load_pipeline", _raise)

    result = asyncio.run(AceStepProvider().run("job-x", {"style": "lofi"}))

    assert result.success is False
    assert result.output_path is None
    assert "ace-step" in result.error


def test_unavailable_pipeline_none_fails_gracefully(monkeypatch):
    # _load_pipeline이 None을 돌려줘도 graceful 실패 (AC6).
    monkeypatch.setattr(ace_step_provider, "_load_pipeline", lambda: None)

    result = asyncio.run(AceStepProvider().run("job-x", {"style": "lofi"}))

    assert result.success is False
    assert result.output_path is None


def test_happy_path_param_mapping_and_save(monkeypatch, tmp_path):
    # stand-in 주입 후: style_prompt→prompt, duration_seconds→audio_duration 매핑과
    # OUTPUT_DIR/{job_id}/music/ 저장·output_path 반환을 실제 코드로 검증 (AC2,3,4,11c).
    stand_in = _StandInPipeline()
    monkeypatch.setattr(ace_step_provider, "_load_pipeline", lambda: stand_in)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)

    result = asyncio.run(
        AceStepProvider().run(
            "job-happy",
            {"style_prompt": "synthwave kpop", "duration_seconds": 45},
        )
    )

    assert result.success is True, result.error
    out = Path(result.output_path)
    assert out.exists()
    assert out.parent == tmp_path / "job-happy" / "music"

    call = stand_in.calls[0]
    assert call["prompt"] == "synthwave kpop"
    assert call["audio_duration"] == 45.0
    assert result.metadata["audio_duration"] == 45.0


def test_default_duration_and_style_fallback(monkeypatch, tmp_path):
    # duration 없으면 기본값, style_prompt 없으면 style로 fallback (AC2).
    stand_in = _StandInPipeline()
    monkeypatch.setattr(ace_step_provider, "_load_pipeline", lambda: stand_in)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)

    result = asyncio.run(AceStepProvider().run("job-def", {"style": "ambient"}))

    assert result.success is True, result.error
    call = stand_in.calls[0]
    assert call["prompt"] == "ambient"
    assert call["audio_duration"] == ace_step_provider.DEFAULT_DURATION_SECONDS


def test_save_wav_file_writes_readable_wav(tmp_path):
    # 호환 패치 #2(torchcodec 우회) 실코드 검증: (channels, samples) 텐서를 전치해
    # soundfile로 지정 경로에 읽을 수 있는 wav를 쓴다. stand-in 테스트는 이 경로를 안 타므로
    # 여기서 직접 검증한다(모델 불필요, 목 금지).
    import soundfile as sf
    import torch

    target = torch.zeros(2, 100)  # (channels, samples) 스테레오
    out = tmp_path / "music" / "ace_step.wav"

    returned = ace_step_provider._save_wav_file(
        target, 0, save_path=str(out), sample_rate=16000
    )

    assert returned == str(out)
    assert out.exists()
    data, sr = sf.read(str(out))
    assert sr == 16000
    assert data.shape == (100, 2)  # (samples, channels)로 전치 저장


def test_first_audio_path_selects_first_string():
    # ACE-Step __call__ 반환 [경로들..., params dict]에서 첫 문자열 경로를 고른다.
    assert ace_step_provider._first_audio_path(["a.wav", {"k": 1}]) == "a.wav"
    assert ace_step_provider._first_audio_path([{"k": 1}]) is None  # 경로 없으면 None
    assert ace_step_provider._first_audio_path([]) is None
    assert ace_step_provider._first_audio_path(None) is None
