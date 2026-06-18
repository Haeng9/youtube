"""runner 출력 전달 테스트 (Story 2-1, AC9).

무거운 실제 provider(Demucs)나 외부 API(Suno) 없이, runner가 한 step의 출력을 다음
step params로 누적 전달하는지만 검증한다. provider/update_job을 가짜로 주입한다.
"""
from app.pipeline import runner
from app.pipeline.providers.base import ProviderResult


def test_separation_output_flows_to_music_reference(monkeypatch):
    captured = {}

    class _Sep:
        async def run(self, job_id, params):
            return ProviderResult(
                success=True,
                output_path="/out/job/stems/no_vocals.wav",
                metadata={"vocals": "/out/job/stems/vocals.wav"},
            )

    class _Recorder:
        """이후 step들은 받은 params를 기록하고 성공만 반환."""

        async def run(self, job_id, params):
            captured[params.get("_step")] = dict(params)
            return ProviderResult(success=True)

    def fake_get_active_provider(step):
        # _step 키로 어느 step의 params인지 식별 가능하게 표시
        provider = _Sep() if step == "separation" else _Recorder()
        return provider

    # 각 step params에 step 이름을 심어 기록 키로 쓰기 위해 runner params를 가로채는 대신
    # provider.run 안에서 식별하려고 step을 params에 주입하는 래퍼를 둔다.
    real_steps = runner.PIPELINE_STEPS

    def patched_get(step):
        prov = fake_get_active_provider(step)
        orig_run = prov.run

        async def run(job_id, params):
            params["_step"] = step
            return await orig_run(job_id, params)

        prov.run = run
        return prov

    monkeypatch.setattr(runner, "get_active_provider", patched_get)
    monkeypatch.setattr(runner, "update_job", lambda *a, **k: None)

    runner.run_pipeline("job-1", "/in/song.mp3", "synthwave")

    # music step이 separation의 출력(MR)을 reference_audio_path로 받았는지 (AC9)
    assert captured["music"]["reference_audio_path"] == "/out/job/stems/no_vocals.wav"
    assert captured["music"]["separation_output"] == "/out/job/stems/no_vocals.wav"
    # separation metadata도 누적 전달됨
    assert captured["music"]["vocals"] == "/out/job/stems/vocals.wav"
    # 원본 style은 그대로 유지
    assert captured["music"]["style"] == "synthwave"
