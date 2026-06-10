"""스텁(stub) provider — 실제 AI 로직 없이 성공 결과만 반환한다.
이후 스토리(1.4 Demucs, 2.1 Suno 등)에서 단계별 실제 구현으로 교체된다."""
from app.pipeline.providers.base import (
    BaseSeparationProvider,
    BaseMusicProvider,
    BaseImageProvider,
    BaseVideoProvider,
    ProviderResult,
)


class StubSeparationProvider(BaseSeparationProvider):
    async def run(self, job_id, params) -> ProviderResult:
        return ProviderResult(success=True, output_path=None, error=None, metadata={})


class StubMusicProvider(BaseMusicProvider):
    async def run(self, job_id, params) -> ProviderResult:
        return ProviderResult(success=True, output_path=None, error=None, metadata={})


class StubImageProvider(BaseImageProvider):
    async def run(self, job_id, params) -> ProviderResult:
        return ProviderResult(success=True, output_path=None, error=None, metadata={})


class StubVideoProvider(BaseVideoProvider):
    async def run(self, job_id, params) -> ProviderResult:
        return ProviderResult(success=True, output_path=None, error=None, metadata={})
