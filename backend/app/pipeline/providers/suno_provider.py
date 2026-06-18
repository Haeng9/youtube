"""Suno 음악 생성 provider (Story 2-1).

분리된 MR(no_vocals) + 스타일 프롬프트를 Suno API(비공식/커뮤니티 게이트웨이)에 보내
AI 커버 음악을 생성하고, 완성된 오디오를 data/outputs/{job_id}/music/ 에 저장한다.
music stub을 대체한다.

Suno는 공식 공개 API가 없다. SUNO_API_KEY가 비어 있으면 네트워크 호출 없이 graceful하게
실패한다(AC4). 실제 엔드포인트/요청 스키마는 커뮤니티 래퍼(gcui-art/suno-api) 기준이며,
키 확보 후 선택한 게이트웨이 문서로 재검증해야 한다. 교체가 쉽도록 엔드포인트/상수는
이 파일 상단 한 곳에 모아둔다.
"""
import asyncio
import re
from urllib.parse import urlparse

import httpx

from app import config
from app.pipeline.providers.base import BaseMusicProvider, ProviderResult

# --- 커뮤니티 Suno API 스펙 (키 확보 후 재검증 필요) ---
GENERATE_PATH = "/api/generate"
GET_PATH = "/api/get"

POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 600  # 10분 (AC5)
REQUEST_TIMEOUT_SECONDS = 60


def _as_clip_list(data):
    """generate/get 응답을 클립 리스트로 정규화. 게이트웨이마다 list 또는
    {clips:[...]} / {data:[...]} 모양이 섞여 있어 모두 수용한다."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if isinstance(data.get("clips"), list):
            return data["clips"]
        if isinstance(data.get("data"), list):
            return data["data"]
        return [data]
    return []


def _first_clip(data):
    clips = _as_clip_list(data)
    return clips[0] if clips else None


def _safe_filename(clip_id: str) -> str:
    """비공식 게이트웨이가 돌려준 clip_id에 '/'·'..'가 있어도 music 디렉터리 밖으로
    경로 탈출하지 못하도록 안전 문자(영숫자/-/_)만 남긴다."""
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", clip_id)
    return safe or "clip"


class SunoProvider(BaseMusicProvider):
    async def run(self, job_id, params) -> ProviderResult:
        if not config.SUNO_API_KEY:
            return ProviderResult(
                success=False,
                error="SUNO_API_KEY 미설정 — .env에 키를 넣어주세요",
            )

        try:
            base = config.SUNO_API_BASE.rstrip("/")
            style_prompt = params.get("style_prompt") or params.get("style") or ""
            lyrics = params.get("lyrics")
            reference_audio_path = params.get("reference_audio_path")

            headers = {"Authorization": f"Bearer {config.SUNO_API_KEY}"}
            payload = {
                "prompt": lyrics or "",
                "tags": style_prompt,
                "make_instrumental": lyrics is None,
                "wait_audio": False,
            }

            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                gen_resp = await client.post(
                    base + GENERATE_PATH, json=payload, headers=headers
                )
                gen_resp.raise_for_status()
                clip = _first_clip(gen_resp.json())
                clip_id = (clip or {}).get("id")
                if not clip_id:
                    return ProviderResult(
                        success=False, error="generate 응답에 작업 id가 없습니다"
                    )

                audio_url = await self._poll_until_complete(
                    client, base, clip_id, headers
                )
                if audio_url is None:
                    return ProviderResult(
                        success=False,
                        error=f"폴링 타임아웃 — {POLL_TIMEOUT_SECONDS}s 내 완료되지 않음",
                    )

                music_dir = config.OUTPUT_DIR / str(job_id) / "music"
                music_dir.mkdir(parents=True, exist_ok=True)
                out_path = music_dir / f"{_safe_filename(clip_id)}.mp3"

                # audio_url이 API와 다른 호스트(CDN/S3 등)면 Authorization 헤더를
                # 보내지 않는다 — SUNO_API_KEY가 제3자 호스트로 유출되지 않게.
                same_host = urlparse(audio_url).netloc == urlparse(base).netloc
                audio_resp = await client.get(
                    audio_url, headers=headers if same_host else {}
                )
                audio_resp.raise_for_status()
                out_path.write_bytes(audio_resp.content)

            return ProviderResult(
                success=True,
                output_path=str(out_path),
                metadata={
                    "clip_id": clip_id,
                    "audio_url": audio_url,
                    "reference_audio_path": reference_audio_path,
                },
            )
        except Exception as e:
            return ProviderResult(success=False, error=f"{type(e).__name__}: {e}")

    async def _poll_until_complete(self, client, base, clip_id, headers):
        """status가 'complete'가 될 때까지 폴링. 타임아웃 시 None 반환.
        블로킹 sleep 금지 — asyncio.sleep 사용(이벤트 루프 비차단)."""
        elapsed = 0
        while elapsed < POLL_TIMEOUT_SECONDS:
            resp = await client.get(
                base + GET_PATH, params={"ids": clip_id}, headers=headers
            )
            resp.raise_for_status()
            clip = _first_clip(resp.json())
            status = (clip or {}).get("status")
            if status == "complete":
                return clip.get("audio_url")
            if status in ("error", "failed"):
                # 실패 상태는 10분 타임아웃까지 기다리지 않고 즉시 실패로 전달.
                raise RuntimeError(f"클립 생성 실패 — status={status}")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            elapsed += POLL_INTERVAL_SECONDS
        return None
