from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import UPLOAD_DIR, OUTPUT_DIR, MODELS_DIR, ALLOWED_ORIGINS
from app.api import upload, jobs, download

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="YouTube AI Pipeline", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(download.router, prefix="/api")


@app.get("/")
async def root():
    return {"status": "ok", "message": "YouTube AI Pipeline API"}
