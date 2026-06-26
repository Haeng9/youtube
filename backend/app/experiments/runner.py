"""A/B 실험 러너 (Story 4-1).

한 입력(job)에 대해 한 step의 '모든' 등록 provider(활성/비활성 무관)를 같은
params로 실행하고, 각 결과를 experiments 테이블에 기록한다. 같은 입력 + 다른
provider = A/B 비교(예: music step에서 Suno vs ACE-Step)."""
import asyncio
from typing import List, Optional

from app.experiments.store import record_experiment
from app.pipeline.providers.loader import list_step_providers


def run_experiment(
    job_id: str,
    step: str,
    params: dict,
    provider_names: Optional[List[str]] = None,
) -> list:
    """step의 후보 provider들을 같은 params로 돌려 결과를 experiments에 기록.

    provider_names가 주어지면 그 부분집합만, 아니면 step의 모든 provider.
    한 provider가 실패/예외여도 나머지를 계속 실행하고, 실패 행은 result_path=None
    으로 기록한다(A/B가 한 쪽 실패로 중단되지 않게). 기록된 Experiment 목록 반환."""
    candidates = list_step_providers(step)
    if provider_names is not None:
        wanted = set(provider_names)
        candidates = [(name, prov) for name, prov in candidates if name in wanted]

    recorded = []
    for name, provider in candidates:
        result_path = None
        try:
            result = asyncio.run(provider.run(job_id, params))
            if result.success:
                result_path = result.output_path
        except Exception:
            # provider 자체가 던진 예외도 A/B를 막지 않는다 — 실패로 기록만.
            result_path = None
        recorded.append(record_experiment(job_id, step, name, result_path))

    return recorded
