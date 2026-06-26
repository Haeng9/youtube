"""FFmpeg 기반 최종 합성 provider (Story 3-3) — 파이프라인의 5번째이자 마지막 단계.

앞 단계 산출물을 하나의 YouTube용 MP4로 합친다:
  - 음악(music 단계 오디오)  → audio_path / music_output
  - 영상(video 단계 clip.mp4) → video_path / video_output
  - 커버(image 단계 cover.png)→ cover_image_path / image_output
결과를 data/outputs/{job_id}/output.mp4 에 저장한다.

오디오·영상 길이 정합: LTX 클립(~2s)이 음악(수십 초~분)보다 짧으므로 `-stream_loop -1`로
영상을 무한 반복하고 `-shortest`로 오디오 길이에서 출력을 종료한다(짧은 쪽=유한한 오디오).
영상이 없고 커버만 있으면 커버를 `-loop 1` 정지영상으로 합성한다.

16:9 + 정규화: 출력은 기본 1280×720(16:9). 입력 비율이 달라도 scale+pad로 왜곡 없이
레터박스하고 오디오는 loudnorm(EBU R128, YouTube -14 LUFS)으로 정규화한다.

ffmpeg는 시스템 바이너리(런타임 필수 의존성, Demucs/LTX에서 이미 사용)를 subprocess로 호출한다.
ffmpeg 미설치/비정상 종료/입력 부재는 예외를 밖으로 던지지 않고 graceful 실패로 변환한다.
"""
import shutil
import subprocess

from app import config
from app.pipeline.providers.base import BaseSynthesisProvider, ProviderResult

# size 미지정/형식 불일치 시 기본 출력 해상도. 16:9 (YouTube HD).
DEFAULT_SIZE = (1280, 720)

# 오디오 정규화 필터 — EBU R128, YouTube 권장 타깃(-14 LUFS, TP -1.5 dBTP).
LOUDNORM_FILTER = "loudnorm=I=-14:TP=-1.5:LRA=11"

# 커버 정지영상 모드의 프레임레이트.
COVER_FPS = 24


def _ffmpeg_bin():
    """시스템 ffmpeg 경로를 찾는다. 없으면 None (호출부가 graceful 실패로 변환)."""
    return shutil.which("ffmpeg")


def _parse_size(size):
    """size를 (width, height)로 정규화. [w, h] 형태만 수용하고, 없거나 형식이 다르면 기본값.
    길이 2여도 원소가 정수로 변환되지 않으면 기본값 (3-1/3-2 _parse_size 계약)."""
    if isinstance(size, (list, tuple)) and len(size) == 2:
        try:
            return int(size[0]), int(size[1])
        except (TypeError, ValueError):
            return DEFAULT_SIZE
    return DEFAULT_SIZE


def _build_command(ffmpeg, mode, visual_path, audio_path, out_path, width, height):
    """ffmpeg 인자 리스트를 만든다(순수함수). mode='video'면 영상 무한 루프, 'cover'면 정지영상.
    공통: 입력 비율을 왜곡 없이 16:9 캔버스에 레터박스(scale+pad+setsar), 오디오 loudnorm 정규화,
    libx264/yuv420p + aac, `-shortest`로 오디오 길이에서 종료, +faststart(스트리밍 친화)."""
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p"
    )

    cmd = [ffmpeg, "-y"]
    if mode == "video":
        # 영상을 무한 반복 — `-shortest`가 오디오 길이에서 끊는다.
        cmd += ["-stream_loop", "-1", "-i", str(visual_path)]
    else:
        # 커버 정지 이미지를 반복.
        cmd += ["-loop", "1", "-i", str(visual_path)]
    cmd += ["-i", str(audio_path)]

    cmd += [
        "-map", "0:v:0",   # 시각 = 첫 입력(영상/커버)
        "-map", "1:a:0",   # 오디오 = 둘째 입력(음악) — 영상에 트랙이 있어도 음악 사용
        "-vf", vf,
        "-af", LOUDNORM_FILTER,
        "-c:v", "libx264",
        "-preset", "medium",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
    ]
    if mode == "cover":
        cmd += ["-r", str(COVER_FPS)]
    cmd += [
        "-shortest",
        "-movflags", "+faststart",
        str(out_path),
    ]
    return cmd


def _run_ffmpeg(cmd):
    """ffmpeg를 실행한다(의존성 seam). 비정상 종료 시 CalledProcessError를 올리며 호출부가
    graceful 실패로 변환한다. stderr를 캡처해 에러 메시지에 쓴다."""
    subprocess.run(cmd, check=True, capture_output=True)


class FfmpegSynthesisProvider(BaseSynthesisProvider):
    async def run(self, job_id, params) -> ProviderResult:
        # 오디오는 필수 — 음악 단계 산출물.
        audio_path = params.get("audio_path") or params.get("music_output")
        if not audio_path:
            return ProviderResult(
                success=False,
                error="synthesis 단계 오디오(audio_path)가 없습니다 — music 단계 산출물 필요",
            )

        # 시각 소스: 영상(우선) 또는 커버. 둘 다 없으면 진행 불가.
        video_path = params.get("video_path") or params.get("video_output")
        cover_path = params.get("cover_image_path") or params.get("image_output")
        if video_path:
            mode, visual_path = "video", video_path
        elif cover_path:
            mode, visual_path = "cover", cover_path
        else:
            return ProviderResult(
                success=False,
                error="synthesis 단계 시각 소스가 없습니다 — video 클립 또는 cover 이미지 필요",
            )

        ffmpeg = _ffmpeg_bin()
        if ffmpeg is None:
            return ProviderResult(
                success=False,
                error="시스템 ffmpeg를 찾을 수 없습니다 (PATH에 ffmpeg 필요 — 런타임 필수 의존성)",
            )

        try:
            # 출력 해상도는 전용 키 output_size로 읽는다 — 공용 size 키는 upstream(image SDXL
            # 1024², video LTX 512×288)이 metadata로 흘려보내 runner가 params에 누적하므로,
            # 그걸 읽으면 합성 출력이 마지막 writer(LTX) 크기로 끌려간다. 전용 키로 격리해
            # AC4 기본값(1280×720 YouTube HD)을 보장한다.
            width, height = _parse_size(params.get("output_size"))

            out_dir = config.OUTPUT_DIR / str(job_id)
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / "output.mp4"

            cmd = _build_command(
                ffmpeg, mode, visual_path, audio_path, out_path, width, height
            )
            _run_ffmpeg(cmd)

            return ProviderResult(
                success=True,
                output_path=str(out_path),
                metadata={
                    "mode": mode,
                    "audio_path": str(audio_path),
                    "visual_path": str(visual_path),
                    "size": [width, height],
                },
            )
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or b"")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            # stderr 끝부분(실제 에러)이 진단에 유용 — 너무 길지 않게 자른다.
            tail = stderr.strip()[-500:]
            return ProviderResult(
                success=False, error=f"ffmpeg 합성 실패 (exit {e.returncode}): {tail}"
            )
        except Exception as e:
            return ProviderResult(success=False, error=f"{type(e).__name__}: {e}")
