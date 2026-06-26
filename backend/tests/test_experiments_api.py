"""experiments API 테스트 (Story 4-1) — 실 FastAPI TestClient + 실 DB(목 금지).

POST의 무거운 실행만 스레드 타깃(run_experiment)을 가벼운 대역으로 치환해 회피한다
(엔드포인트 응답/candidates/202 검증용 — orchestration 경계). 러너 자체 로직은
test_experiment_runner.py에서 실검증한다.
"""
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.experiments.store import record_experiment
from app.jobs.queue import create_job

client = TestClient(app)


def test_get_experiments_grouped():
    job = create_job("api_group.mp3", "jazz")
    record_experiment(job.job_id, "music", "suno", "/out/api/music/suno.wav")
    record_experiment(job.job_id, "music", "ace_step", "/out/api/music/ace_step.wav")

    res = client.get("/api/experiments")
    assert res.status_code == 200
    groups = res.json()["groups"]
    grp = next(g for g in groups if g["job_id"] == job.job_id)
    assert grp["filename"] == "api_group.mp3"
    names = {e["provider_name"] for e in grp["experiments"]}
    assert {"suno", "ace_step"} <= names


def test_post_run_returns_candidates(monkeypatch):
    # 무거운 실 provider 실행 회피 — 스레드 타깃만 대역으로.
    monkeypatch.setattr("app.api.experiments.run_experiment", lambda *a, **k: [])
    job = create_job("api_run.mp3", "kpop")

    res = client.post("/api/experiments/run", json={"job_id": job.job_id, "step": "music"})
    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "started"
    assert "suno" in body["candidates"]
    assert "ace_step" in body["candidates"]


def test_post_run_provider_names_narrows_candidates(monkeypatch):
    monkeypatch.setattr("app.api.experiments.run_experiment", lambda *a, **k: [])
    job = create_job("api_narrow.mp3", "kpop")
    res = client.post(
        "/api/experiments/run",
        json={"job_id": job.job_id, "step": "music", "provider_names": ["suno", "ace_step"]},
    )
    assert res.status_code == 202
    assert set(res.json()["candidates"]) == {"suno", "ace_step"}


def test_post_run_unknown_job_404(monkeypatch):
    monkeypatch.setattr("app.api.experiments.run_experiment", lambda *a, **k: [])
    res = client.post("/api/experiments/run", json={"job_id": "nope", "step": "music"})
    assert res.status_code == 404


def test_post_run_no_candidates_400(monkeypatch):
    monkeypatch.setattr("app.api.experiments.run_experiment", lambda *a, **k: [])
    job = create_job("api_nostep.mp3", "lofi")
    res = client.post("/api/experiments/run", json={"job_id": job.job_id, "step": "does_not_exist"})
    assert res.status_code == 400


def test_get_result_serves_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    job = create_job("api_result.mp3", "jazz")
    out = tmp_path / job.job_id / "music" / "suno.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"RIFFfake")
    exp = record_experiment(job.job_id, "music", "suno", str(out))

    res = client.get(f"/api/experiments/{exp.id}/result")
    assert res.status_code == 200
    assert res.content == b"RIFFfake"
    assert res.headers["content-type"].startswith("audio/")


def test_get_result_path_traversal_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    job = create_job("api_evil.mp3", "jazz")
    # OUTPUT_DIR 밖을 가리키는 경로 → 400
    exp = record_experiment(job.job_id, "music", "evil", "C:/Windows/system.ini")

    res = client.get(f"/api/experiments/{exp.id}/result")
    assert res.status_code == 400


def test_get_result_sibling_prefix_dir_blocked(tmp_path, monkeypatch):
    # startswith 가드의 허점 회귀: OUTPUT_DIR와 접두를 공유하는 형제 디렉터리
    # (예: outputs_evil)는 차단되어야 한다(is_relative_to 검사).
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    monkeypatch.setattr(config, "OUTPUT_DIR", output_dir)

    sibling = tmp_path / "outputs_evil"
    sibling.mkdir()
    leak = sibling / "secret.wav"
    leak.write_bytes(b"leak")

    job = create_job("api_sibling.mp3", "jazz")
    exp = record_experiment(job.job_id, "music", "evil", str(leak))
    res = client.get(f"/api/experiments/{exp.id}/result")
    assert res.status_code == 400


def test_get_result_missing_404(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    job = create_job("api_missing.mp3", "jazz")
    exp = record_experiment(job.job_id, "music", "gone", str(tmp_path / job.job_id / "nope.wav"))
    res = client.get(f"/api/experiments/{exp.id}/result")
    assert res.status_code == 404


def test_put_score():
    job = create_job("api_score.mp3", "pop")
    exp = record_experiment(job.job_id, "music", "suno", "/out/s/music/suno.wav")
    res = client.put(f"/api/experiments/{exp.id}/score", json={"score": 4})
    assert res.status_code == 200
    assert res.json()["score"] == 4


def test_put_score_missing_404():
    res = client.put("/api/experiments/99999999/score", json={"score": 1})
    assert res.status_code == 404
