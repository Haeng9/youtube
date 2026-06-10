from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProviderResult:
    """파이프라인 각 단계(provider)의 실행 결과."""
    success: bool
    output_path: Optional[str] = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class BaseSeparationProvider:
    """보컬/반주 분리 단계 추상 인터페이스."""

    async def run(self, job_id, params) -> ProviderResult:
        raise NotImplementedError


class BaseMusicProvider:
    """음악 생성 단계 추상 인터페이스."""

    async def run(self, job_id, params) -> ProviderResult:
        raise NotImplementedError


class BaseImageProvider:
    """커버 이미지 생성 단계 추상 인터페이스."""

    async def run(self, job_id, params) -> ProviderResult:
        raise NotImplementedError


class BaseVideoProvider:
    """최종 영상 합성 단계 추상 인터페이스."""

    async def run(self, job_id, params) -> ProviderResult:
        raise NotImplementedError
