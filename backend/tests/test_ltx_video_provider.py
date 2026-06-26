"""LtxVideoProvider 테스트 (Story 3-2).

목 금지 — LTX 실모델은 수 GB라 테스트에서 못 띄운다(OD=B 실생성은 smoke로). 대신 외부
diffusers 파이프라인과 영상 export를 가벼운 대역(stand-in)으로 주입(seam 2개)해 우리
오케스트레이션 로직(이미지 로드/파라미터 매핑/프레임 추출/저장/반환/graceful 실패)을 실제
코드로 검증한다.
"""
import asyncio
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from app import config
from app.pipeline.providers import ltx_video_provider
from app.pipeline.providers.base import BaseVideoProvider
from app.pipeline.providers.ltx_video_provider import LtxVideoProvider


class _StandInPipeline:
    """diffusers LTX 파이프라인의 가벼운 대역 — 받은 kwargs를 기록하고 작은 PIL 프레임들을
    담은 `.frames`(= [[img, ...]])를 반환(실제 LTXPipelineOutput과 동일한 형태: 첫 비디오=frames[0])."""

    def __init__(self, n_frames=3):
        self.calls = []
        self.n_frames = n_frames

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        w = kwargs.get("width", 8)
        h = kwargs.get("height", 8)
        frames = [Image.new("RGB", (w, h), "black") for _ in range(self.n_frames)]
        return SimpleNamespace(frames=[frames])


def _make_image(tmp_path, name="cover.png", size=(64, 64)):
    p = tmp_path / name
    Image.new("RGB", size, "white").save(str(p))
    return str(p)


def test_ltx_is_video_provider():
    assert isinstance(LtxVideoProvider(), BaseVideoProvider)


def test_missing_image_path_fails_gracefully():
    # i2v 입력 이미지가 없으면 네트워크/모델 없이 success=False로 graceful 실패해야 한다 (AC7).
    result = asyncio.run(LtxVideoProvider().run("job-x", {"style": "neon city"}))
    assert result.success is False
    assert result.output_path is None
    assert "image_path" in result.error


def test_unavailable_pipeline_importerror_fails_gracefully(monkeypatch, tmp_path):
    # diffusers 미설치(ImportError) 시 예외를 던지지 않고 success=False로 떨어져야 한다 (AC6).
    def _raise():
        raise ImportError("No module named 'diffusers'")

    monkeypatch.setattr(ltx_video_provider, "_load_pipeline", _raise)

    result = asyncio.run(
        LtxVideoProvider().run("job-x", {"image_path": _make_image(tmp_path)})
    )

    assert result.success is False
    assert result.output_path is None
    assert "LTX-Video" in result.error


def test_unavailable_pipeline_none_fails_gracefully(monkeypatch, tmp_path):
    # _load_pipeline이 None을 돌려줘도 graceful 실패 (AC6).
    monkeypatch.setattr(ltx_video_provider, "_load_pipeline", lambda: None)

    result = asyncio.run(
        LtxVideoProvider().run("job-x", {"image_path": _make_image(tmp_path)})
    )

    assert result.success is False
    assert result.output_path is None


def test_happy_path_param_mapping_and_save(monkeypatch, tmp_path):
    # stand-in 2개(pipeline + export) 주입 후: image 로드, prompt/negative_prompt 매핑,
    # size→width/height, duration→num_frames, OUTPUT_DIR/{job_id}/video/clip.mp4 저장·output_path
    # 반환을 실제 코드로 검증 (AC2,3,4,11c).
    stand_in = _StandInPipeline()
    monkeypatch.setattr(ltx_video_provider, "_load_pipeline", lambda: stand_in)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)

    exported = {}

    def _fake_export(frames, path, fps):
        exported["frames"] = frames
        exported["fps"] = fps
        Path(path).write_bytes(b"\x00\x00\x00\x18ftypmp42")  # 작은 MP4-ish 바이트

    monkeypatch.setattr(ltx_video_provider, "_export_video", _fake_export)

    image_path = _make_image(tmp_path)
    result = asyncio.run(
        LtxVideoProvider().run(
            "job-happy",
            {
                "image_path": image_path,
                "prompt": "slow zoom over neon city, cinematic",
                "negative_prompt": "blurry, distorted",
                "size": [704, 480],
                "duration_seconds": 2,
            },
        )
    )

    assert result.success is True, result.error
    out = Path(result.output_path)
    assert out.exists()
    assert out.name == "clip.mp4"
    assert out.parent == tmp_path / "job-happy" / "video"

    call = stand_in.calls[0]
    assert call["prompt"] == "slow zoom over neon city, cinematic"
    assert call["negative_prompt"] == "blurry, distorted"
    assert call["width"] == 704
    assert call["height"] == 480
    # 2s @ 24fps = 48 → 8k+1 정규화 = 49
    assert call["num_frames"] == 49
    assert call["frame_rate"] == ltx_video_provider.DEFAULT_FPS
    # pipeline이 받은 image는 우리가 로드한 PIL 이미지여야 한다.
    assert isinstance(call["image"], Image.Image)

    assert result.metadata["size"] == [704, 480]
    assert result.metadata["num_frames"] == 49
    # export로 fps가 전달되고, 프레임 리스트가 넘어갔는지(첫 비디오 frames[0]) 확인.
    assert exported["fps"] == ltx_video_provider.DEFAULT_FPS
    assert len(exported["frames"]) == stand_in.n_frames


def test_happy_path_passes_first_video_frames_to_export(monkeypatch, tmp_path):
    # _frames_from_output가 frames[0](첫 비디오의 프레임 리스트)을 export로 넘기는지 명시 검증.
    stand_in = _StandInPipeline(n_frames=5)
    monkeypatch.setattr(ltx_video_provider, "_load_pipeline", lambda: stand_in)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)

    captured = {}

    def _fake_export(frames, path, fps):
        captured["n"] = len(frames)
        Path(path).write_bytes(b"x")

    monkeypatch.setattr(ltx_video_provider, "_export_video", _fake_export)

    result = asyncio.run(
        LtxVideoProvider().run(
            "job-frames", {"image_path": _make_image(tmp_path), "style": "lofi"}
        )
    )
    assert result.success is True, result.error
    assert captured["n"] == 5


def test_default_size_duration_and_style_fallback(monkeypatch, tmp_path):
    # size/duration 없으면 기본값, prompt 없으면 style로 fallback, image_output fallback도 동작 (AC2).
    stand_in = _StandInPipeline()
    monkeypatch.setattr(ltx_video_provider, "_load_pipeline", lambda: stand_in)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(ltx_video_provider, "_export_video", lambda f, p, fps: Path(p).write_bytes(b"x"))

    result = asyncio.run(
        LtxVideoProvider().run(
            "job-def", {"image_output": _make_image(tmp_path), "style": "ambient forest"}
        )
    )

    assert result.success is True, result.error
    call = stand_in.calls[0]
    assert call["prompt"] == "ambient forest"
    assert call["negative_prompt"] == ""
    assert (call["width"], call["height"]) == ltx_video_provider.DEFAULT_SIZE
    # 기본 duration 2s @ 24fps → 49
    assert call["num_frames"] == 49


def test_empty_frames_fails_gracefully(monkeypatch, tmp_path):
    # 파이프라인이 빈 프레임을 반환하면 export 없이 graceful 실패.
    class _EmptyPipeline:
        def __call__(self, **kwargs):
            return SimpleNamespace(frames=[])

    monkeypatch.setattr(ltx_video_provider, "_load_pipeline", lambda: _EmptyPipeline())
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)

    result = asyncio.run(
        LtxVideoProvider().run("job-empty", {"image_path": _make_image(tmp_path)})
    )
    assert result.success is False
    assert "프레임" in result.error


def test_parse_size_pure():
    # [w,h]만 수용, 그 외(None/길이 불일치/문자열)는 기본값. 정수 변환 불가도 기본값 (3-1 계약).
    assert ltx_video_provider._parse_size([704, 480]) == (704, 480)
    assert ltx_video_provider._parse_size((512, 288)) == (512, 288)
    assert ltx_video_provider._parse_size(None) == ltx_video_provider.DEFAULT_SIZE
    assert ltx_video_provider._parse_size([512]) == ltx_video_provider.DEFAULT_SIZE
    assert ltx_video_provider._parse_size("512x288") == ltx_video_provider.DEFAULT_SIZE
    assert ltx_video_provider._parse_size(["512", "bad"]) == ltx_video_provider.DEFAULT_SIZE
    assert ltx_video_provider._parse_size(["704", "480"]) == (704, 480)


def test_resolve_num_frames_pure():
    # duration·fps → 8k+1 정규화. 없거나 비정상이면 기본 2s. 최소 9.
    assert ltx_video_provider._resolve_num_frames(2, 24) == 49      # 48 → 49
    assert ltx_video_provider._resolve_num_frames(1, 24) == 25      # 24 → 25
    assert ltx_video_provider._resolve_num_frames(None, 24) == 49   # 기본 2s
    assert ltx_video_provider._resolve_num_frames("bad", 24) == 49  # 변환 실패 → 기본
    assert ltx_video_provider._resolve_num_frames(0, 24) == 49      # 0 → 기본
    # 결과는 항상 8k+1 형태.
    n = ltx_video_provider._resolve_num_frames(3, 24)
    assert (n - 1) % 8 == 0


def test_frames_from_output_selects_first_video():
    # `.frames`의 첫 비디오(frames[0])를 고른다. 리스트 직접 반환도 수용. 비면 None.
    vid = [Image.new("RGB", (4, 4))]
    assert ltx_video_provider._frames_from_output(SimpleNamespace(frames=[vid])) is vid
    assert ltx_video_provider._frames_from_output([vid]) is vid
    assert ltx_video_provider._frames_from_output(SimpleNamespace(frames=[])) is None
    assert ltx_video_provider._frames_from_output([]) is None
