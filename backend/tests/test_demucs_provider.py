"""DemucsProvider 통합 테스트 (Story 1-4).

실제 모델을 돌리되, 커밋된 MP3 대신 합성 톤(사인파)을 생성해 입력으로 쓴다
(Decision 2-b). 첫 실행 시 htdemucs 가중치(수백 MB)가 torch hub 캐시로 다운로드된다.
"""
import asyncio
import math
import struct
import wave
from pathlib import Path

from app.pipeline.providers.demucs_provider import DemucsProvider


def _make_sine_wav(path, seconds=2, sr=44100, freq=440.0):
    """16-bit 스테레오 PCM 사인파 WAV를 표준 라이브러리로 생성."""
    n = int(seconds * sr)
    frames = bytearray()
    for i in range(n):
        val = int(0.3 * 32767 * math.sin(2 * math.pi * freq * i / sr))
        frames += struct.pack("<hh", val, val)
    with wave.open(str(path), "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))


def test_demucs_separates_synthetic_tone(tmp_path):
    input_path = tmp_path / "tone.wav"
    _make_sine_wav(input_path)

    provider = DemucsProvider()
    result = asyncio.run(provider.run("test-demucs", {"input_path": str(input_path)}))

    assert result.success is True, result.error
    vocals = Path(result.metadata["vocals"])
    no_vocals = Path(result.metadata["no_vocals"])
    assert vocals.exists()
    assert no_vocals.exists()
    # 44-byte WAV 헤더만 있는 빈 파일이 아니라 실제 오디오 프레임이 쓰였는지 확인
    assert vocals.stat().st_size > 44
    assert no_vocals.stat().st_size > 44
    assert result.output_path == str(no_vocals)
