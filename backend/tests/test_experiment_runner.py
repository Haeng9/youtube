"""A/B 러너 테스트 (Story 4-1) — 목 금지: 실 stand-in provider + 실 .wav 파일.

stand-in은 mock이 아니라 진짜 BaseMusicProvider 서브클래스로, 진짜 wav 파일을 쓴다.
무거운 AI 모델(Suno/ACE-Step) 없이 A/B 기록 루프·같은-params 전달·실패 처리를
실코드로 검증한다. list_step_providers seam에 주입(test_runner.py가 get_active_provider를
주입하는 것과 동일한 방식).
"""
import wave

from app import config
from app.experiments import runner
from app.experiments.store import get_experiment
from app.jobs.queue import create_job
from app.pipeline.providers.base import BaseMusicProvider, ProviderResult
from app.pipeline.providers.loader import list_step_providers


def _write_tiny_wav(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * 100)


class _StandInProvider(BaseMusicProvider):
    """진짜 wav 파일을 쓰는 실 provider 대역. 받은 params를 기록한다."""

    def __init__(self, name, seen):
        self.name = name
        self.seen = seen

    async def run(self, job_id, params):
        self.seen[self.name] = dict(params)
        out = config.OUTPUT_DIR / str(job_id) / "music" / f"{self.name}.wav"
        _write_tiny_wav(out)
        return ProviderResult(success=True, output_path=str(out))


class _FailingProvider(BaseMusicProvider):
    async def run(self, job_id, params):
        return ProviderResult(success=False, error="no api key")


def test_ab_runs_all_providers_same_params(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    seen = {}
    monkeypatch.setattr(
        runner,
        "list_step_providers",
        lambda step: [
            ("standin_a", _StandInProvider("standin_a", seen)),
            ("standin_b", _StandInProvider("standin_b", seen)),
        ],
    )

    job = create_job("ab.mp3", "jazz")
    params = {"input_path": "/in/ab.mp3", "style": "jazz"}
    recorded = runner.run_experiment(job.job_id, "music", params)

    # 두 provider 모두 실행 + 같은 params 전달 (같은 입력 A/B의 핵심)
    assert seen["standin_a"]["style"] == "jazz"
    assert seen["standin_b"]["style"] == "jazz"
    assert seen["standin_a"] == seen["standin_b"]

    # 실 wav 파일 2개 생성
    assert (tmp_path / job.job_id / "music" / "standin_a.wav").exists()
    assert (tmp_path / job.job_id / "music" / "standin_b.wav").exists()

    # experiments 2건 기록(실 DB)
    assert len(recorded) == 2
    for exp in recorded:
        assert get_experiment(exp.id).result_path is not None


def test_failed_provider_recorded_with_null_path(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    seen = {}
    monkeypatch.setattr(
        runner,
        "list_step_providers",
        lambda step: [
            ("ok", _StandInProvider("ok", seen)),
            ("fails", _FailingProvider()),
        ],
    )

    job = create_job("ab_fail.mp3", "pop")
    recorded = runner.run_experiment(job.job_id, "music", {"style": "pop"})

    by_name = {e.provider_name: e for e in recorded}
    assert get_experiment(by_name["ok"].id).result_path is not None
    assert get_experiment(by_name["fails"].id).result_path is None


def test_provider_names_filter(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    seen = {}
    monkeypatch.setattr(
        runner,
        "list_step_providers",
        lambda step: [
            ("a", _StandInProvider("a", seen)),
            ("b", _StandInProvider("b", seen)),
        ],
    )
    job = create_job("ab_filter.mp3", "lofi")
    recorded = runner.run_experiment(job.job_id, "music", {"style": "lofi"}, provider_names=["b"])
    assert [e.provider_name for e in recorded] == ["b"]
    assert "a" not in seen


def test_db_loading_includes_inactive_candidates():
    """실 DB 로딩 경로: A/B 후보가 활성(Suno)뿐 아니라 비활성(ACE-Step)도 포함하는지.
    provider를 실제로 실행하진 않고 후보 목록만 확인(무거운 모델 회피)."""
    names = [name for name, _ in list_step_providers("music")]
    assert "suno" in names
    assert "ace_step" in names
