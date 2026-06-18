"""SunoProvider 테스트 (Story 2-1).

목(mock) 금지 — 키 미설정 경로는 네트워크 없이 즉시 실패하고, happy path는 표준
라이브러리 http.server로 띄운 로컬 스텁이 generate→poll→audio 응답을 돌려주면
실제 httpx가 그 서버를 쳐서 폴링/다운로드 로직을 그대로 검증한다. 실 Suno 호출은 보류.
"""
import asyncio
import http.server
import json
import threading
from pathlib import Path

import pytest

from app import config
from app.pipeline.providers import suno_provider
from app.pipeline.providers.base import BaseMusicProvider
from app.pipeline.providers.suno_provider import SunoProvider

AUDIO_BYTES = b"ID3-fake-mp3-payload"


class _StubHandler(http.server.BaseHTTPRequestHandler):
    base_url = ""           # 서버 시작 후 fixture가 채움
    poll_counts: dict = {}  # clip_id별 GET /api/get 호출 횟수 (폴링 반복 검증용)

    def log_message(self, *args):  # 테스트 출력 조용히
        pass

    def _send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        if self.path.startswith(suno_provider.GENERATE_PATH):
            self._send_json([{"id": "clip-123"}])
        else:
            self._send_json({"error": "not found"}, 404)

    def do_GET(self):
        if self.path.startswith(suno_provider.GET_PATH):
            # 첫 폴링은 submitted, 두 번째에 complete → 폴링 루프 반복을 강제
            n = _StubHandler.poll_counts.get("clip-123", 0) + 1
            _StubHandler.poll_counts["clip-123"] = n
            if n >= 2:
                self._send_json(
                    [{
                        "id": "clip-123",
                        "status": "complete",
                        "audio_url": _StubHandler.base_url + "/audio/clip-123",
                    }]
                )
            else:
                self._send_json([{"id": "clip-123", "status": "submitted"}])
        elif self.path.startswith("/audio/"):
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(AUDIO_BYTES)))
            self.end_headers()
            self.wfile.write(AUDIO_BYTES)
        else:
            self._send_json({"error": "not found"}, 404)


@pytest.fixture
def stub_server():
    _StubHandler.poll_counts = {}
    server = http.server.HTTPServer(("127.0.0.1", 0), _StubHandler)
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    _StubHandler.base_url = base_url
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield base_url
    finally:
        server.shutdown()
        server.server_close()


class _FailHandler(http.server.BaseHTTPRequestHandler):
    """generate는 id를 주지만 폴링에서 status=failed를 반환 → 타임아웃이 아닌 즉시 실패."""

    def log_message(self, *args):
        pass

    def _send_json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        self._send_json([{"id": "clip-fail"}])

    def do_GET(self):
        self._send_json([{"id": "clip-fail", "status": "failed"}])


@pytest.fixture
def fail_server():
    server = http.server.HTTPServer(("127.0.0.1", 0), _FailHandler)
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield base_url
    finally:
        server.shutdown()
        server.server_close()


def test_suno_provider_is_music_provider():
    assert isinstance(SunoProvider(), BaseMusicProvider)


def test_safe_filename_blocks_path_traversal():
    # 게이트웨이가 '/'·'..'가 든 clip_id를 줘도 파일명에 경로 구분자가 남지 않아야 한다.
    assert "/" not in suno_provider._safe_filename("../../etc/passwd")
    assert "\\" not in suno_provider._safe_filename("..\\..\\x")
    assert suno_provider._safe_filename("clip-123") == "clip-123"


def test_failed_status_fails_fast_not_timeout(monkeypatch, fail_server):
    # status=failed는 10분 타임아웃까지 기다리지 않고 즉시 실패로 전달돼야 한다(폴링 patch).
    monkeypatch.setattr(config, "SUNO_API_KEY", "dummy-key")
    monkeypatch.setattr(config, "SUNO_API_BASE", fail_server)
    monkeypatch.setattr(suno_provider, "POLL_INTERVAL_SECONDS", 0.01)

    result = asyncio.run(SunoProvider().run("job-fail", {"style": "lofi"}))

    assert result.success is False
    assert "타임아웃" not in result.error
    assert "failed" in result.error


def test_no_key_fails_without_network(monkeypatch):
    # 베이스를 가짜 주소로 둬도 키가 없으면 네트워크 호출 없이 즉시 실패해야 한다(AC4).
    monkeypatch.setattr(config, "SUNO_API_KEY", "")
    monkeypatch.setattr(config, "SUNO_API_BASE", "http://127.0.0.1:1")  # 연결되면 실패할 주소

    result = asyncio.run(SunoProvider().run("job-nokey", {"style": "lofi"}))

    assert result.success is False
    assert "SUNO_API_KEY" in result.error
    assert result.output_path is None


def test_happy_path_generate_poll_download(monkeypatch, stub_server, tmp_path):
    monkeypatch.setattr(config, "SUNO_API_KEY", "dummy-key")
    monkeypatch.setattr(config, "SUNO_API_BASE", stub_server)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(suno_provider, "POLL_INTERVAL_SECONDS", 0.01)

    result = asyncio.run(
        SunoProvider().run(
            "job-happy",
            {"style_prompt": "synthwave", "reference_audio_path": "/mr/no_vocals.wav"},
        )
    )

    assert result.success is True, result.error
    out = Path(result.output_path)
    assert out.exists()
    assert out.read_bytes() == AUDIO_BYTES
    assert out.parent == tmp_path / "job-happy" / "music"
    assert result.metadata["clip_id"] == "clip-123"
    # 폴링이 최소 2회 돌아 complete까지 갔는지 (submitted→complete)
    assert _StubHandler.poll_counts["clip-123"] >= 2
