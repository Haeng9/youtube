from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import DATABASE_URL

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Create backend/.env with a DATABASE_URL "
        "(see _bmad-output/implementation-artifacts/1-2-db-setup.md)."
    )

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
