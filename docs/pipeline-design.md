# AI 음악 파이프라인 설계 문서

> 작성일: 2026-06-10 | 기반: 비바체 채널 분석 + AI 기술 조사

---

## 1. 레퍼런스 채널 분석 — 비바체(@vi-va-ce)

### 실제 파이프라인 (댓글 전수 분석으로 확인)

```
원곡 MP3
  → MR 제거 (Demucs 추정) — "답은 MR제거에 있습니다"
  → Suno에 레퍼런스 + 번역 가사 + 스타일 프롬프트 입력
  → Suno 다량 생성 후 최고 결과 선택 (크레딧 다량 소모)
  → Suno Stems/MIDI/Studio 후편집
  → 가사 번역: ChatGPT → Gemini 검증
  → 이미지: Midjourney (Niji Journey) / Gemini / Grok
  → 영상: Grok Aurora (i2v) — "감성 때문에 그록 선호"
  → FFmpeg 합성
```

### 핵심 인사이트
- **RVC 사용 안 함** — 직접 확인: "RVC는 사용되지 않았고 suno만 사용되었습니다"
- **Suno가 보컬+반주 동시 생성** — 별도 보컬 변환 불필요
- **스타일 프롬프트에 아티스트명 사용** — "누자베스, 바운디, 도쿄플래시 느낌으로"
- **수익화 전략**: 커버곡은 수익화 포기, 오리지널 창작곡만 수익화 계획
- **현재 한계**: Suno 저작권 강화로 최근 작업 막힘 ("저도 못하고 있어요")

---

## 2. 최종 파이프라인 설계 (C 방향)

### 방향: Provider 패턴 — 각 스텝 교체 가능

```
원곡 MP3 / 텍스트 프롬프트
  → [Step 1] 음원 분리 Provider
  → [Step 2] 음악 생성 Provider  ← 핵심 스텝
  → [Step 3] 이미지 생성 Provider
  → [Step 4] 영상 생성 Provider
  → [Step 5] FFmpeg 합성
  → 결과물 MP4
```

### Step별 Provider 옵션

| Step | Provider A | Provider B | Provider C |
|------|-----------|-----------|-----------|
| 음원 분리 | Demucs (로컬) | python-audio-separator | — |
| 음악 생성 | **Suno API** | ACE-Step (로컬) | DiffRhythm (로컬) |
| 이미지 생성 | Midjourney API | Stable Diffusion (로컬) | Flux (로컬) |
| 영상 생성 | **Grok Aurora** | Seedance 2.0 (fal.ai) | Kling v3 (fal.ai) |

### 설계 원칙
- 각 Step은 인터페이스(추상 클래스)로 정의
- 구현체는 config 또는 DB 설정으로 교체
- A/B/C Provider 결과를 비교 실험 가능한 구조

---

## 3. 시스템 아키텍처

### 최종 목표: 웹 서비스 (SaaS)

```
[Frontend - Vue 3]
    ↕ REST API
[Backend - FastAPI]
    ↕
[Job Queue - Celery + Redis]  ← Phase 2
    ↕
[Pipeline Workers]
    ├── Step 1: 음원 분리
    ├── Step 2: 음악 생성 (Provider 선택)
    ├── Step 3: 이미지 생성 (Provider 선택)
    ├── Step 4: 영상 생성 (Provider 선택)
    └── Step 5: FFmpeg 합성
    ↕
[Storage - S3 / 로컬]  ← Phase 2
    ↕
[DB - PostgreSQL]  ← Phase 2 (현재: SQLite)
```

### DB 설계 (초안)

- **DB**: MySQL (Phase 1부터 적용, SQLite 사용 안 함)
- **ORM**: SQLAlchemy + Alembic (마이그레이션)

```sql
users         -- user=1 시작, SaaS 전환 시 확장
jobs          -- 현재 _jobs 인메모리 대체
job_steps     -- 각 스텝 상태/결과 추적
providers     -- 사용 가능한 Provider 목록 + 설정
experiments   -- Provider별 결과 비교 데이터
```

---

## 4. Phase 로드맵

### Phase 1 (현재) — 로컬 검증
- user=1 (본인만 사용)
- SQLite DB
- 인메모리 큐 → DB 큐
- Provider 패턴 뼈대 구현
- Suno + Grok 조합으로 첫 결과물 생성

### Phase 2 — 서버 배포
- PostgreSQL
- Celery + Redis 큐
- S3 파일 스토리지
- 멀티유저 지원

### Phase 3 — SaaS
- 결제 시스템
- Provider 자동 선택 (품질/비용 최적화)
- 대시보드

---

## 5. 다음 작업 우선순위

1. **DB 도입** — SQLite + SQLAlchemy, `_jobs` 인메모리 교체
2. **Provider 인터페이스 설계** — 추상 클래스 정의
3. **Suno Provider 구현** — Step 2 첫 번째 구현체
4. **Grok Provider 구현** — Step 4 첫 번째 구현체
5. **실험 결과 비교 기능** — 같은 입력에 여러 Provider 결과 저장/비교
