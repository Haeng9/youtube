"""SdxlProvider 테스트 (Story 3-1).

목 금지 — SDXL 실모델은 ~7GB라 테스트에서 못 띄운다(보류 결정, 실생성은 smoke로). 대신 외부
diffusers 파이프라인을 가벼운 대역(stand-in)으로 주입(seam)해 우리 오케스트레이션 로직(파라미터
매핑/출력 경로/저장/graceful 실패)을 실제 코드로 검증한다.
"""
import asyncio
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from app import config
from app.pipeline.providers import sdxl_provider
from app.pipeline.providers.base import BaseImageProvider
from app.pipeline.providers.sdxl_provider import SdxlProvider


class _StandInPipeline:
    """diffusers SDXL 파이프라인의 가벼운 대역 — 받은 kwargs를 기록하고 작은 PIL 이미지를
    담은 `.images` 리스트를 반환(실제 StableDiffusionXLPipelineOutput와 동일한 형태)."""

    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        img = Image.new("RGB", (kwargs.get("width", 8), kwargs.get("height", 8)), "black")
        return SimpleNamespace(images=[img])


def test_sdxl_is_image_provider():
    assert isinstance(SdxlProvider(), BaseImageProvider)


def test_unavailable_pipeline_importerror_fails_gracefully(monkeypatch):
    # diffusers 미설치(ImportError) 시 예외를 던지지 않고 success=False로 떨어져야 한다 (AC6).
    def _raise():
        raise ImportError("No module named 'diffusers'")

    monkeypatch.setattr(sdxl_provider, "_load_pipeline", _raise)

    result = asyncio.run(SdxlProvider().run("job-x", {"style": "lofi cover art"}))

    assert result.success is False
    assert result.output_path is None
    assert "SDXL" in result.error


def test_unavailable_pipeline_none_fails_gracefully(monkeypatch):
    # _load_pipeline이 None을 돌려줘도 graceful 실패 (AC6).
    monkeypatch.setattr(sdxl_provider, "_load_pipeline", lambda: None)

    result = asyncio.run(SdxlProvider().run("job-x", {"style": "lofi"}))

    assert result.success is False
    assert result.output_path is None


def test_happy_path_param_mapping_and_save(monkeypatch, tmp_path):
    # stand-in 주입 후: prompt/negative_prompt 매핑, size→width/height, OUTPUT_DIR/{job_id}/image/
    # cover.png 저장·output_path 반환을 실제 코드로 검증 (AC2,3,4,11c).
    stand_in = _StandInPipeline()
    monkeypatch.setattr(sdxl_provider, "_load_pipeline", lambda: stand_in)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)

    result = asyncio.run(
        SdxlProvider().run(
            "job-happy",
            {
                "prompt": "synthwave album cover, neon city",
                "negative_prompt": "blurry, text",
                "size": [1024, 576],
            },
        )
    )

    assert result.success is True, result.error
    out = Path(result.output_path)
    assert out.exists()
    assert out.name == "cover.png"
    assert out.parent == tmp_path / "job-happy" / "image"

    call = stand_in.calls[0]
    assert call["prompt"] == "synthwave album cover, neon city"
    assert call["negative_prompt"] == "blurry, text"
    assert call["width"] == 1024
    assert call["height"] == 576
    assert result.metadata["size"] == [1024, 576]


def test_default_size_and_style_fallback(monkeypatch, tmp_path):
    # size 없으면 기본 1024², prompt 없으면 style로 fallback (AC2).
    stand_in = _StandInPipeline()
    monkeypatch.setattr(sdxl_provider, "_load_pipeline", lambda: stand_in)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)

    result = asyncio.run(SdxlProvider().run("job-def", {"style": "ambient forest"}))

    assert result.success is True, result.error
    call = stand_in.calls[0]
    assert call["prompt"] == "ambient forest"
    assert call["negative_prompt"] == ""
    assert (call["width"], call["height"]) == sdxl_provider.DEFAULT_SIZE


def test_parse_size_pure():
    # [w,h]만 수용, 그 외(None/길이 불일치/문자열)는 기본값 (순수함수, 모델 불필요).
    assert sdxl_provider._parse_size([800, 600]) == (800, 600)
    assert sdxl_provider._parse_size((1344, 768)) == (1344, 768)
    assert sdxl_provider._parse_size(None) == sdxl_provider.DEFAULT_SIZE
    assert sdxl_provider._parse_size([1024]) == sdxl_provider.DEFAULT_SIZE
    assert sdxl_provider._parse_size("1024x1024") == sdxl_provider.DEFAULT_SIZE
    # 길이 2여도 원소가 정수 변환 불가하면 기본값으로 fallback (계약: 형식 불일치 → 기본).
    assert sdxl_provider._parse_size(["1024", "bad"]) == sdxl_provider.DEFAULT_SIZE
    assert sdxl_provider._parse_size([None, None]) == sdxl_provider.DEFAULT_SIZE
    # 숫자 문자열은 정상 변환(유효 입력).
    assert sdxl_provider._parse_size(["800", "600"]) == (800, 600)


def test_first_image_selects_first():
    # `.images` 리스트의 첫 이미지를 고른다. 리스트 직접 반환도 수용. 비면 None.
    img = Image.new("RGB", (4, 4))
    assert sdxl_provider._first_image(SimpleNamespace(images=[img])) is img
    assert sdxl_provider._first_image([img]) is img
    assert sdxl_provider._first_image(SimpleNamespace(images=[])) is None
    assert sdxl_provider._first_image([]) is None
