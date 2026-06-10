import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

UPLOAD_DIR = BASE_DIR / "data" / "uploads"
OUTPUT_DIR = BASE_DIR / "data" / "outputs"
MODELS_DIR = BASE_DIR / "data" / "models"

ENV = os.getenv("ENV", "local")

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:8000",
]
