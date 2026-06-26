"""experiments 테이블 영속화 (Story 4-1).

같은 입력을 서로 다른 provider로 돌린 A/B 결과를 기록하고, 입력(job_id)별로
묶어 조회한다. 기존 jobs/queue.py의 SessionLocal try/finally 패턴을 따른다."""
from typing import List, Optional

from app.db import SessionLocal
from app.db.models import Experiment, Job


def record_experiment(
    job_id: str,
    step: str,
    provider_name: str,
    result_path: Optional[str],
    score: Optional[int] = None,
) -> Experiment:
    db = SessionLocal()
    try:
        exp = Experiment(
            job_id=job_id,
            step=step,
            provider_name=provider_name,
            result_path=result_path,
            score=score,
        )
        db.add(exp)
        db.commit()
        db.refresh(exp)
        return exp
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_experiment(exp_id: int) -> Optional[Experiment]:
    db = SessionLocal()
    try:
        return db.get(Experiment, exp_id)
    finally:
        db.close()


def set_score(exp_id: int, score: int) -> Optional[Experiment]:
    db = SessionLocal()
    try:
        exp = db.get(Experiment, exp_id)
        if exp is None:
            return None
        exp.score = score
        db.commit()
        db.refresh(exp)
        return exp
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def list_experiments_grouped() -> List[dict]:
    """모든 experiment를 입력(job_id)별로 묶어 반환. 최신 입력(job created_at)이 먼저,
    그룹 내 experiment는 생성순. 각 그룹은 비교에 필요한 job 메타(filename/style) 포함."""
    db = SessionLocal()
    try:
        exps = db.query(Experiment).order_by(Experiment.id).all()
        if not exps:
            return []

        job_ids = {e.job_id for e in exps}
        jobs = {j.job_id: j for j in db.query(Job).filter(Job.job_id.in_(job_ids)).all()}

        groups: dict[str, dict] = {}
        for e in exps:
            grp = groups.get(e.job_id)
            if grp is None:
                job = jobs.get(e.job_id)
                grp = {
                    "job_id": e.job_id,
                    "filename": job.filename if job else None,
                    "style": job.style if job else None,
                    "created_at": job.created_at.isoformat() if job and job.created_at else None,
                    "experiments": [],
                }
                groups[e.job_id] = grp
            grp["experiments"].append(
                {
                    "id": e.id,
                    "step": e.step,
                    "provider_name": e.provider_name,
                    "result_path": e.result_path,
                    "score": e.score,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
            )

        # 최신 입력이 먼저: job created_at desc (없으면 맨 뒤)
        return sorted(
            groups.values(),
            key=lambda g: g["created_at"] or "",
            reverse=True,
        )
    finally:
        db.close()
