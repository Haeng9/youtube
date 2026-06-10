# Story 1-1: YouTube AI Pipeline - 프로젝트 초기 설정

## Status: review

## Story
**As a** 개발자(현국씨),
**I want** FastAPI 백엔드와 Vue 3 프론트엔드로 구성된 프로젝트 골격을 갖추고 싶다,
**So that** AI 파이프라인을 로컬에서 실행하고 웹 UI로 MP3를 업로드해 영상을 만들 수 있다.

## Acceptance Criteria
- AC1: `backend/` 폴더에 FastAPI 앱이 있고 `py -3.12 run.py`로 실행되며 `http://localhost:8000`에서 응답한다.
- AC2: `GET /` 는 `{"status": "ok"}` JSON을 반환한다.
- AC3: `POST /api/upload` 는 MP3 파일과 style 파라미터를 받아 job_id를 반환한다.
- AC4: `GET /api/jobs/{job_id}` 는 작업 상태(pending/processing/done/failed)와 메시지를 반환한다.
- AC5: `GET /api/download/{job_id}` 는 완성된 파일을 다운로드한다.
- AC6: `frontend/` 폴더에 Vue 3 앱이 있고 `npm run dev`로 실행되며 `http://localhost:5173`에서 응답한다.
- AC7: Vue 앱에 3개 화면이 있다: Upload(MP3 드래그앤드롭 + 스타일 선택), Progress(진행상황 폴링), Result(다운로드).
- AC8: 백엔드와 프론트엔드 CORS 설정이 되어있어 서로 통신 가능하다.
- AC9: `backend/data/uploads/`, `backend/data/outputs/`, `backend/data/models/` 디렉토리가 자동 생성된다.
- AC10: `backend/app/pipeline/runner.py`에 5단계 파이프라인 골격(TODO 주석)이 있다.

## Tasks/Subtasks

- [x] Task 1: 백엔드 FastAPI 프로젝트 구조 생성
  - [x] 1.1 폴더 구조 생성 (app/api, app/pipeline, app/jobs, app/storage, data/*)
  - [x] 1.2 app/config.py - 경로 및 CORS 설정
  - [x] 1.3 app/jobs/queue.py - 인메모리 작업 큐 (Job, JobStatus, create/get/update)
  - [x] 1.4 app/pipeline/runner.py - 5단계 파이프라인 골격 (TODO 주석)
  - [x] 1.5 app/api/upload.py - POST /api/upload 엔드포인트
  - [x] 1.6 app/api/jobs.py - GET /api/jobs/{job_id} 엔드포인트
  - [x] 1.7 app/api/download.py - GET /api/download/{job_id} 엔드포인트
  - [x] 1.8 app/main.py - FastAPI 앱, CORS 미들웨어, 라우터 등록
  - [x] 1.9 run.py - uvicorn 실행 진입점
  - [x] 1.10 requirements.txt 작성

- [x] Task 2: 프론트엔드 Vue 3 프로젝트 생성
  - [x] 2.1 npm create vue@latest로 Vue 3 앱 생성
  - [x] 2.2 src/router/index.js - 3개 라우트 (/, /progress/:jobId, /result/:jobId)
  - [x] 2.3 src/views/UploadView.vue - 드래그앤드롭 + 스타일 선택 + 업로드
  - [x] 2.4 src/views/ProgressView.vue - 2초 폴링으로 상태 표시
  - [x] 2.5 src/views/ResultView.vue - 영상 미리보기 + 다운로드
  - [x] 2.6 src/App.vue, src/main.js - 라우터 연결

- [x] Task 3: 통합 검증
  - [x] 3.1 백엔드 AC 검증 통과 (TestClient)
  - [x] 3.2 프론트엔드 빌드 성공 (npm run build)
  - [x] 3.3 CORS 미들웨어 설정 완료

## Dev Notes

### 기술 스택
- **백엔드**: Python 3.12.10, FastAPI, uvicorn, python-multipart, aiofiles
- **프론트엔드**: Vue 3, Vue Router
- **실행**: `py -3.12` 명령어 사용 (Python 3.15 alpha 공존)
- **GPU**: RTX 3060 12GB (AI 모델 단계에서 사용 예정)

### 디렉토리 구조
```
D:/youtube/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── upload.py
│   │   │   ├── jobs.py
│   │   │   └── download.py
│   │   ├── pipeline/
│   │   │   ├── __init__.py
│   │   │   └── runner.py
│   │   ├── jobs/
│   │   │   ├── __init__.py
│   │   │   └── queue.py
│   │   └── storage/
│   │       └── __init__.py
│   ├── data/
│   │   ├── uploads/
│   │   ├── outputs/
│   │   └── models/
│   ├── requirements.txt
│   └── run.py
└── frontend/
    └── (Vue 3 앱)
```

### 파이프라인 스텝 순서 (runner.py에 TODO로 표시)
1. Demucs - 보컬/반주 분리
2. RVC - 보컬 스타일 변환
3. MusicGen - 반주 재생성
4. Stable Diffusion - 커버 이미지 생성
5. FFmpeg - 최종 영상 합성

### Phase 구조
- Phase 1 (현재): 로컬 실행, 인메모리 큐, 로컬 파일 저장
- Phase 2 (추후): Celery+Redis, S3, gunicorn+nginx

## Dev Agent Record

### Implementation Plan
_작성 예정_

### Debug Log
_작성 예정_

### Completion Notes
_작성 예정_

## File List
- backend/app/__init__.py
- backend/app/main.py
- backend/app/config.py
- backend/app/api/__init__.py
- backend/app/api/upload.py
- backend/app/api/jobs.py
- backend/app/api/download.py
- backend/app/pipeline/__init__.py
- backend/app/pipeline/runner.py
- backend/app/jobs/__init__.py
- backend/app/jobs/queue.py
- backend/app/storage/__init__.py
- backend/run.py
- backend/requirements.txt
- backend/.gitignore
- frontend/src/App.vue
- frontend/src/main.js
- frontend/src/router/index.js
- frontend/src/views/UploadView.vue
- frontend/src/views/ProgressView.vue
- frontend/src/views/ResultView.vue

## Change Log
- 2026-06-10: 초기 프로젝트 구조 생성. FastAPI 백엔드 + Vue 3 프론트엔드. 모든 AC 통과.
