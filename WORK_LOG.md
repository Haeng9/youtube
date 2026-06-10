# YouTube AI Pipeline - 작업 일지

## 프로젝트 개요

**목표:** AI를 활용해 음악 영상을 자동 제작하는 파이프라인을 개발하고, 이를 유튜브 채널로 운영 + 추후 SaaS 서비스로 판매

**레퍼런스 채널:** 비바체 (@vi-va-ce)
- K-POP/J-POP 원곡을 AI로 다른 장르 스타일로 커버
- 3개월 만에 구독자 38,400명, 최고 조회수 35만
- 콘텐츠 전략은 따라하되, 수익 구조는 다르게 가야 함 (오리지널 AI 음악 목표)

---

## 기술 스택

| 구분 | 기술 | 비고 |
|---|---|---|
| 백엔드 | FastAPI + uvicorn | Python 3.12.10 사용 |
| 프론트엔드 | Vue 3 | |
| AI 모델 | Demucs, RVC, MusicGen, Stable Diffusion | 모두 오픈소스, 로컬 GPU 실행 |
| GPU | RTX 3060 (12GB VRAM) | |
| 영상 합성 | FFmpeg | |
| 배포 (Phase 2) | gunicorn + nginx | |

---

## 프로젝트 구조

```
D:/youtube/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 앱 진입점
│   │   ├── config.py            # 경로 및 환경 설정
│   │   ├── api/
│   │   │   ├── upload.py        # POST /api/upload
│   │   │   ├── jobs.py          # GET /api/jobs/<id>
│   │   │   └── download.py      # GET /api/download/<id>
│   │   ├── pipeline/
│   │   │   └── runner.py        # 파이프라인 실행 조율 (스텝별 TODO)
│   │   ├── jobs/
│   │   │   └── queue.py         # 작업 상태 관리 (인메모리)
│   │   └── storage/             # 파일 저장소 추상화
│   ├── data/
│   │   ├── uploads/             # 업로드된 원본 MP3
│   │   ├── outputs/             # 완성된 영상
│   │   └── models/              # AI 모델 가중치 (git 제외)
│   ├── requirements.txt
│   └── run.py                   # python run.py 로 실행
│
└── frontend/
    ├── src/
    │   ├── views/
    │   │   ├── UploadView.vue   # 1화면: MP3 업로드 + 스타일 선택
    │   │   ├── ProgressView.vue # 2화면: 처리 진행 상황 (2초 폴링)
    │   │   └── ResultView.vue   # 3화면: 영상 미리보기 + 다운로드
    │   ├── router/index.js
    │   ├── App.vue
    │   └── main.js
    └── package.json
```

---

## 실행 방법

```bash
# 백엔드 (터미널 1)
cd D:/youtube/backend
py -3.12 run.py
# → http://localhost:8000

# 프론트엔드 (터미널 2)
cd D:/youtube/frontend
npm run dev
# → http://localhost:5173
```

---

## AI 파이프라인 구현 현황

| 스텝 | 모델 | 상태 |
|---|---|---|
| 1. 보컬/반주 분리 | Demucs (Meta) | ⬜ TODO |
| 2. 보컬 스타일 변환 | RVC | ⬜ TODO |
| 3. 반주 재생성 | MusicGen (Meta) | ⬜ TODO |
| 4. 커버 이미지 생성 | Stable Diffusion | ⬜ TODO |
| 5. 영상 합성 | FFmpeg | ⬜ TODO |

> `backend/app/pipeline/runner.py` 에 각 스텝 주석처리로 골격만 있음.
> 다음 세션에서 **Demucs 설치 + Step 1 (보컬/반주 분리) 구현**부터 시작.

## 완료된 작업 (Story 1-1)

- FastAPI 백엔드 골격 완성 (upload, jobs, download API)
- Vue 3 프론트엔드 완성 (UploadView, ProgressView, ResultView)
- 모든 AC 검증 통과
- 스토리 파일: `_bmad-output/implementation-artifacts/1-1-project-setup.md`

## 완료된 작업 (2026-06-10 — 코드 리뷰 & 보안 패치)

코드 리뷰 (Blind Hunter + Edge Case Hunter) 수행 후 아래 패치 적용:

| 파일 | 수정 내용 |
|---|---|
| `backend/app/api/upload.py` | Path Traversal 차단 (UUID + `Path.name`), 파일명 None 체크, 50MB 크기 제한, `shutil` 제거 |
| `backend/app/api/download.py` | `output_file` 경로가 OUTPUT_DIR 밖을 가리키는 경우 차단 (`.resolve()` 검증) |
| `backend/run.py` | `ENV=local`일 때만 `reload=True` (프로덕션 안전) |
| `frontend/src/views/UploadView.vue` | `res.ok` 체크 후 서버 에러 메시지 표시 |
| `frontend/src/views/ProgressView.vue` | 404 / 비-JSON 응답 시 폴링 타이머 중단 + 실패 메시지 표시 |

**의도적 deferred (Phase 2 때 처리):**
- `_jobs` 인메모리 구조 → Celery+Redis로 교체 시 해결
- 쓰레드 무제한 생성 → 파이프라인 구현 시 ThreadPoolExecutor로 교체
- MIME 타입 검증 → libmagic 또는 파일 헤더 검사 추가 예정

**다음 세션:** Demucs 설치 + Step 1 (보컬/반주 분리) 구현

---

## Phase 로드맵

- **Phase 1 (현재):** 로컬 실행 + 웹 UI로 본인이 직접 사용하며 검증
- **Phase 2:** 서버 배포 + SaaS (인메모리 큐 → Celery+Redis, 로컬 파일 → S3)

---

## 참고 사항

- Python 3.12.10 (안정 버전) 사용. py -3.12 로 실행할 것.
- AI 모델 가중치는 `data/models/`에 보관, git에 올리지 말 것
- RVC 커뮤니티에 이미 학습된 보컬 모델 수천 개 공유됨 (HuggingFace)
