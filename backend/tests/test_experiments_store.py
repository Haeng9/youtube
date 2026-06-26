"""experiments store 테스트 (Story 4-1) — 실 MySQL DB 사용(목 금지).

다른 테스트와 동일하게 실 DB에 붙는다. job_id FK는 실 create_job으로 확보한다.
"""
from app.experiments.store import (
    record_experiment,
    get_experiment,
    set_score,
    list_experiments_grouped,
)
from app.jobs.queue import create_job


def test_record_and_get_experiment():
    job = create_job("exp_store.mp3", "jazz")
    exp = record_experiment(job.job_id, "music", "suno", "/out/x/music/suno.wav")
    assert exp.id is not None
    fetched = get_experiment(exp.id)
    assert fetched.provider_name == "suno"
    assert fetched.step == "music"
    assert fetched.result_path == "/out/x/music/suno.wav"
    assert fetched.score is None


def test_record_failure_keeps_null_result_path():
    job = create_job("exp_fail.mp3", "pop")
    exp = record_experiment(job.job_id, "music", "broken", None)
    assert get_experiment(exp.id).result_path is None


def test_set_score():
    job = create_job("exp_score.mp3", "lofi")
    exp = record_experiment(job.job_id, "music", "ace_step", "/out/y/music/ace_step.wav")
    updated = set_score(exp.id, 5)
    assert updated.score == 5
    assert get_experiment(exp.id).score == 5


def test_set_score_missing_returns_none():
    assert set_score(99999999, 3) is None


def test_list_grouped_by_input():
    job = create_job("exp_group.mp3", "kpop")
    record_experiment(job.job_id, "music", "suno", "/out/g/music/suno.wav")
    record_experiment(job.job_id, "music", "ace_step", "/out/g/music/ace_step.wav")

    groups = list_experiments_grouped()
    grp = next(g for g in groups if g["job_id"] == job.job_id)
    assert grp["filename"] == "exp_group.mp3"
    assert grp["style"] == "kpop"
    names = {e["provider_name"] for e in grp["experiments"]}
    assert names == {"suno", "ace_step"}
