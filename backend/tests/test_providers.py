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
    # 시드된 separation provider가 로딩되어야 한다
    provider = get_active_provider("separation")
    assert provider is not None
    result = asyncio.run(provider.run("job-1", {}))
    assert result.success is True


def test_get_active_provider_unknown_step_returns_none():
    assert get_active_provider("nonexistent-step") is None
