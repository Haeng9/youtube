import asyncio

import pytest

from app.pipeline.providers.base import (
    BaseSeparationProvider,
    BaseMusicProvider,
    BaseImageProvider,
    BaseVideoProvider,
    ProviderResult,
)
from app.pipeline.providers.loader import load_provider, get_active_provider


@pytest.mark.parametrize(
    "base_cls",
    [BaseSeparationProvider, BaseMusicProvider, BaseImageProvider, BaseVideoProvider],
)
def test_abstract_run_raises_not_implemented(base_cls):
    provider = base_cls()
    with pytest.raises(NotImplementedError):
        asyncio.run(provider.run("job-1", {}))


def test_load_provider_resolves_class_path():
    provider = load_provider("app.pipeline.providers.stubs.StubMusicProvider")
    result = asyncio.run(provider.run("job-1", {}))
    assert isinstance(result, ProviderResult)
    assert result.success is True
    assert result.output_path is None


def test_get_active_provider_from_db():
    # 활성 separation provider(DemucsProvider)가 DB에서 로딩되어야 한다.
    # (실제 분리는 통합 테스트 test_demucs_provider.py에서 검증)
    from app.pipeline.providers.demucs_provider import DemucsProvider

    provider = get_active_provider("separation")
    assert isinstance(provider, DemucsProvider)


def test_get_active_music_provider_is_suno():
    # 활성 music provider가 stub이 아니라 SunoProvider여야 한다 (Story 2-1 마이그레이션).
    from app.pipeline.providers.suno_provider import SunoProvider

    provider = get_active_provider("music")
    assert isinstance(provider, SunoProvider)


def test_ace_step_registered_but_music_active_stays_suno():
    # Story 2-2: ace_step는 is_active=False로 등록만 됐으므로 active music은 여전히 suno여야 한다.
    from app.pipeline.providers.suno_provider import SunoProvider

    assert isinstance(get_active_provider("music"), SunoProvider)


def test_get_active_image_provider_is_sdxl():
    # Story 3-1: image step의 active provider가 stub이 아니라 SdxlProvider로 전환됐는지.
    from app.pipeline.providers.sdxl_provider import SdxlProvider

    provider = get_active_provider("image")
    assert isinstance(provider, SdxlProvider)


def test_get_active_video_provider_is_ltx():
    # Story 3-2: video step의 active provider가 stub이 아니라 LtxVideoProvider로 전환됐는지.
    from app.pipeline.providers.ltx_video_provider import LtxVideoProvider

    provider = get_active_provider("video")
    assert isinstance(provider, LtxVideoProvider)


def test_get_active_provider_unknown_step_returns_none():
    assert get_active_provider("nonexistent-step") is None
