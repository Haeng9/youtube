import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent

load_dotenv(BASE_DIR / ".env")

UPLOAD_DIR = BASE_DIR / "data" / "uploads"
OUTPUT_DIR = BASE_DIR / "data" / "outputs"
MODELS_DIR = BASE_DIR / "data" / "models"

ENV = os.getenv("ENV", "local")

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Suno 음악 생성 provider (Story 2-1). 공식 공개 API 없음 — 키/베이스는 기본 빈값,
# 키가 없으면 SunoProvider가 네트워크 호출 없이 graceful 실패한다.
SUNO_API_KEY = os.getenv("SUNO_API_KEY", "")
SUNO_API_BASE = os.getenv("SUNO_API_BASE", "")

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:8000",
]
