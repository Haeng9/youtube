import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, relationship


def _now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=_now)
    jobs = relationship("Job", back_populates="user")


class Job(Base):
    __tablename__ = "jobs"
    job_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, default=1)
    filename = Column(String(255), nullable=False)
    style = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    message = Column(Text, nullable=True)
    output_file = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)
    user = relationship("User", back_populates="jobs")
    steps = relationship("JobStep", back_populates="job")


class JobStep(Base):
    __tablename__ = "job_steps"
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(36), ForeignKey("jobs.job_id"), nullable=False)
    step_name = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    result_path = Column(String(500), nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    job = relationship("Job", back_populates="steps")


class Provider(Base):
    __tablename__ = "providers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    step = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    class_path = Column(String(200), nullable=False)
    config_json = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)


class Experiment(Base):
    __tablename__ = "experiments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(36), ForeignKey("jobs.job_id"), nullable=False)
    step = Column(String(50), nullable=False)
    provider_name = Column(String(100), nullable=False)
    result_path = Column(String(500), nullable=True)
    score = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_now)
