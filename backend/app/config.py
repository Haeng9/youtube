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

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:8000",
]
