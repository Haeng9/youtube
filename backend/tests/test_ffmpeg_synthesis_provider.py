"""FfmpegSynthesisProvider 테스트 (Story 3-3).

목 금지 — ffmpeg는 가볍고 설치된 런타임 필수 의존성이라, 무거운 모델(LTX)과 달리 실제로
합성까지 검증할 수 있다. 두 층위로 검증한다:
  1. seam(`_run_ffmpeg`)을 가벼운 대역으로 주입해 오케스트레이션(입력 추출·모드 결정·명령
     빌드·저장·반환·graceful)을 실코드로 단위 검증.
  2. 실 ffmpeg 통합 — lavfi로 짧은 영상 + 긴 사인파 오디오를 만들고 provider로 합성한 뒤
     ffprobe로 출력 길이(영상 루프)·해상도(16:9)를 검증(ffmpeg/ffprobe 없으면 skip).
"""
import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest

from app import config
from app.pipeline.providers import ffmpeg_synthesis_provider as mod
from app.pipeline.providers.base import BaseSynthesisProvider, ProviderResult
from app.pipeline.providers.ffmpeg_synthesis_provider import FfmpegSynthesisProvider


def _touch(p, data=b"\x00"):
    Path(p).write_bytes(data)
    return str(p)


# --- 인터페이스 -----------------------------------------------------------------

def test_ffmpeg_is_synthesis_provider():
    assert isinstance(FfmpegSynthesisProvider(), BaseSynthesisProvider)


def test_base_synthesis_run_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        asyncio.run(BaseSynthesisProvider().run("job-1", {}))


# --- graceful 실패 --------------------------------------------------------------

def test_missing_audio_fails_gracefully(tmp_path):
    # 오디오(audio_path/music_output)가 없으면 ffmpeg 호출 없이 success=False (AC2,7).
    result = asyncio.run(
        FfmpegSynthesisProvider().run(
            "job-x", {"video_path": _touch(tmp_path / "clip.mp4")}
        )
    )
    assert result.success is False
    assert result.output_path is None
    assert "audio" in result.error


def test_missing_visual_fails_gracefully(tmp_path):
    # 오디오는 있으나 영상도 커버도 없으면 graceful 실패 (AC2,7).
    result = asyncio.run(
        FfmpegSynthesisProvider().run(
            "job-x", {"audio_path": _touch(tmp_path / "music.wav")}
        )
    )
    assert result.success is False
    assert result.output_path is None
    assert "시각" in result.error


def test_ffmpeg_not_installed_fails_gracefully(monkeypatch, tmp_path):
    # ffmpeg가 PATH에 없으면(shutil.which None) graceful 실패 (AC7).
    monkeypatch.setattr(mod, "_ffmpeg_bin", lambda: None)
    result = asyncio.run(
        FfmpegSynthesisProvider().run(
            "job-x",
            {
                "audio_path": _touch(tmp_path / "music.wav"),
                "video_path": _touch(tmp_path / "clip.mp4"),
            },
        )
    )
    assert result.success is False
    assert "ffmpeg" in result.error


def test_ffmpeg_nonzero_exit_fails_gracefully(monkeypatch, tmp_path):
    # ffmpeg가 비정상 종료(CalledProcessError)하면 stderr 일부를 담아 graceful 실패 (AC7).
    monkeypatch.setattr(mod, "_ffmpeg_bin", lambda: "ffmpeg")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)

    def _boom(cmd):
        raise subprocess.CalledProcessError(
            1, cmd, output=b"", stderr=b"Invalid data found when processing input"
        )

    monkeypatch.setattr(mod, "_run_ffmpeg", _boom)

    result = asyncio.run(
        FfmpegSynthesisProvider().run(
            "job-err",
            {
                "audio_path": _touch(tmp_path / "music.wav"),
                "video_path": _touch(tmp_path / "clip.mp4"),
            },
        )
    )
    assert result.success is False
    assert "exit 1" in result.error
    assert "Invalid data" in result.error


# --- seam happy path (오케스트레이션) -------------------------------------------

def test_video_mode_command_and_save(monkeypatch, tmp_path):
    # seam 주입 후: 영상 모드 명령 빌드(stream_loop + map + loudnorm), OUTPUT_DIR/{job}/output.mp4
    # 저장·output_path 반환을 실코드로 검증 (AC2,3,4,5,6).
    monkeypatch.setattr(mod, "_ffmpeg_bin", lambda: "FFMPEG")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)

    captured = {}

    def _fake_run(cmd):
        captured["cmd"] = cmd
        # 출력 경로(마지막 인자)에 산출물 흉내.
        Path(cmd[-1]).write_bytes(b"\x00\x00\x00\x18ftypmp42")

    monkeypatch.setattr(mod, "_run_ffmpeg", _fake_run)

    video = _touch(tmp_path / "clip.mp4")
    audio = _touch(tmp_path / "music.wav")
    result = asyncio.run(
        FfmpegSynthesisProvider().run(
            "job-vid", {"video_path": video, "audio_path": audio}
        )
    )

    assert result.success is True, result.error
    out = Path(result.output_path)
    assert out.exists()
    assert out.name == "output.mp4"
    assert out.parent == tmp_path / "job-vid"

    cmd = captured["cmd"]
    assert cmd[0] == "FFMPEG"
    assert "-stream_loop" in cmd and cmd[cmd.index("-stream_loop") + 1] == "-1"
    assert "-shortest" in cmd
    assert "-map" in cmd  # 영상/오디오 명시 매핑
    af = cmd[cmd.index("-af") + 1]
    assert af == mod.LOUDNORM_FILTER
    # 영상이 첫 입력, 오디오가 둘째 입력.
    i_idxs = [i for i, a in enumerate(cmd) if a == "-i"]
    assert cmd[i_idxs[0] + 1] == video
    assert cmd[i_idxs[1] + 1] == audio
    assert result.metadata["mode"] == "video"
    assert result.metadata["size"] == [1280, 720]


def test_cover_mode_fallback_when_no_video(monkeypatch, tmp_path):
    # 영상이 없고 커버(image_output)만 있으면 커버 정지영상 모드(-loop 1) (AC2,3).
    monkeypatch.setattr(mod, "_ffmpeg_bin", lambda: "ffmpeg")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)

    captured = {}
    monkeypatch.setattr(
        mod, "_run_ffmpeg", lambda cmd: (captured.update(cmd=cmd), Path(cmd[-1]).write_bytes(b"x"))
    )

    cover = _touch(tmp_path / "cover.png")
    result = asyncio.run(
        FfmpegSynthesisProvider().run(
            "job-cov",
            {"image_output": cover, "music_output": _touch(tmp_path / "m.wav")},
        )
    )
    assert result.success is True, result.error
    cmd = captured["cmd"]
    assert "-loop" in cmd and cmd[cmd.index("-loop") + 1] == "1"
    assert "-stream_loop" not in cmd
    assert result.metadata["mode"] == "cover"


def test_leaked_size_ignored_output_size_honored(monkeypatch, tmp_path):
    # 회귀(code-review Finding 1): runner는 image/video 메타데이터의 공용 "size"를 params에
    # 누적한다(예: LTX 512×288). synthesis는 그 누적된 size에 끌려가면 안 되고, 전용
    # output_size만 따라야 한다 → AC4 기본 1280×720 보장.
    monkeypatch.setattr(mod, "_ffmpeg_bin", lambda: "ffmpeg")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    captured = {}
    monkeypatch.setattr(
        mod, "_run_ffmpeg", lambda cmd: (captured.update(cmd=cmd), Path(cmd[-1]).write_bytes(b"x"))
    )

    base_params = {
        "video_path": _touch(tmp_path / "clip.mp4"),
        "audio_path": _touch(tmp_path / "m.wav"),
        "size": [512, 288],  # upstream(LTX)이 흘린 값 — 무시되어야 함
    }

    # output_size 미지정 → 누적 size 무시하고 기본 1280×720
    r1 = asyncio.run(FfmpegSynthesisProvider().run("job-leak", dict(base_params)))
    assert r1.metadata["size"] == [1280, 720]
    assert "scale=1280:720" in captured["cmd"][captured["cmd"].index("-vf") + 1]

    # output_size 지정 → 그 값 사용(공용 size는 여전히 무시)
    r2 = asyncio.run(
        FfmpegSynthesisProvider().run(
            "job-out", {**base_params, "output_size": [1920, 1080]}
        )
    )
    assert r2.metadata["size"] == [1920, 1080]


def test_video_preferred_over_cover(monkeypatch, tmp_path):
    # 영상과 커버가 모두 있으면 영상 모드가 우선 (AC2).
    monkeypatch.setattr(mod, "_ffmpeg_bin", lambda: "ffmpeg")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(mod, "_run_ffmpeg", lambda cmd: Path(cmd[-1]).write_bytes(b"x"))

    result = asyncio.run(
        FfmpegSynthesisProvider().run(
            "job-both",
            {
                "video_output": _touch(tmp_path / "clip.mp4"),
                "image_output": _touch(tmp_path / "cover.png"),
                "music_output": _touch(tmp_path / "m.wav"),
            },
        )
    )
    assert result.metadata["mode"] == "video"


# --- 순수함수 -------------------------------------------------------------------

def test_parse_size_pure():
    assert mod._parse_size([1920, 1080]) == (1920, 1080)
    assert mod._parse_size((1280, 720)) == (1280, 720)
    assert mod._parse_size(None) == mod.DEFAULT_SIZE
    assert mod._parse_size([1280]) == mod.DEFAULT_SIZE
    assert mod._parse_size("1280x720") == mod.DEFAULT_SIZE
    assert mod._parse_size(["1280", "bad"]) == mod.DEFAULT_SIZE
    assert mod._parse_size(["1920", "1080"]) == (1920, 1080)


def test_build_command_video_mode():
    cmd = mod._build_command("ffmpeg", "video", "v.mp4", "a.wav", "out.mp4", 1280, 720)
    assert cmd[:2] == ["ffmpeg", "-y"]
    assert "-stream_loop" in cmd
    assert "-loop" not in cmd
    assert "-shortest" in cmd
    assert "+faststart" in cmd
    assert cmd[-1] == "out.mp4"
    vf = cmd[cmd.index("-vf") + 1]
    assert "scale=1280:720" in vf and "pad=1280:720" in vf and "setsar=1" in vf
    assert "libx264" in cmd and "aac" in cmd


def test_build_command_cover_mode():
    cmd = mod._build_command("ffmpeg", "cover", "c.png", "a.wav", "out.mp4", 1280, 720)
    assert "-loop" in cmd and cmd[cmd.index("-loop") + 1] == "1"
    assert "-stream_loop" not in cmd
    # 정지영상은 프레임레이트를 명시.
    assert "-r" in cmd


# --- 실 ffmpeg 통합 (목 금지, 실 산출물) ----------------------------------------

@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not on PATH",
)
def test_real_ffmpeg_synthesis_loops_video_to_audio_length(monkeypatch, tmp_path):
    # 실 ffmpeg로 합성까지 검증: 1s 영상 + 3s 오디오 → 출력 길이≈3s(영상 루프), 16:9 해상도.
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")

    video = tmp_path / "clip.mp4"
    audio = tmp_path / "music.wav"
    # 1s 영상(640×360, 영상이 오디오보다 짧아 루프 필요), 3s 사인파 오디오 — lavfi 합성.
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=blue:s=640x360:d=1",
         "-pix_fmt", "yuv420p", str(video)],
        check=True, capture_output=True,
    )
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
         str(audio)],
        check=True, capture_output=True,
    )

    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    result = asyncio.run(
        FfmpegSynthesisProvider().run(
            "job-real", {"video_path": str(video), "audio_path": str(audio)}
        )
    )

    assert result.success is True, result.error
    out = Path(result.output_path)
    assert out.exists() and out.stat().st_size > 0

    # ffprobe로 길이·해상도 검증.
    dur = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(out)],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    # 영상은 1s지만 오디오 3s에 맞춰 루프됐는지 — 출력 길이가 ~3s여야 한다.
    assert abs(float(dur) - 3.0) < 0.5, f"expected ~3s, got {dur}"

    wh = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(out)],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert wh == "1280x720", f"expected 16:9 1280x720, got {wh}"


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not on PATH",
)
def test_real_ffmpeg_cover_mode(monkeypatch, tmp_path):
    # 영상 없이 커버(정지영상)만으로도 실 합성되는지 — 출력 길이≈오디오(2s), 16:9.
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")

    cover = tmp_path / "cover.png"
    audio = tmp_path / "music.wav"
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=red:s=512x512:d=1",
         "-frames:v", "1", str(cover)],
        check=True, capture_output=True,
    )
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         str(audio)],
        check=True, capture_output=True,
    )

    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    result = asyncio.run(
        FfmpegSynthesisProvider().run(
            "job-cover-real",
            {"cover_image_path": str(cover), "audio_path": str(audio)},
        )
    )

    assert result.success is True, result.error
    out = Path(result.output_path)
    assert out.exists() and out.stat().st_size > 0
    dur = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(out)],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert abs(float(dur) - 2.0) < 0.5, f"expected ~2s, got {dur}"
