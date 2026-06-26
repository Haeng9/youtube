"""DB의 providers 테이블 설정을 읽어 provider 클래스를 동적으로 로딩한다."""
import importlib
from typing import List, Optional, Tuple

from app.db import SessionLocal
from app.db.models import Provider


def load_provider(class_path: str):
    """'a.b.c.ClassName' 형태의 점(dot) 경로를 import해서 인스턴스를 반환."""
    module_path, cls_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, cls_name)()


def get_active_provider(step: str):
    """해당 step의 활성(is_active) provider를 DB에서 찾아 인스턴스화해 반환.
    없으면 None."""
    db = SessionLocal()
    try:
        row: Optional[Provider] = (
            db.query(Provider)
            .filter(Provider.step == step, Provider.is_active == True)  # noqa: E712
            .order_by(Provider.id)
            .first()
        )
        if row is None:
            return None
        return load_provider(row.class_path)
    finally:
        db.close()


def list_step_providers(step: str) -> List[Tuple[str, object]]:
    """해당 step에 등록된 '모든' provider를 id 순으로 (name, instance)로 반환.
    get_active_provider와 달리 is_active를 무시한다 — A/B 비교(Story 4-1)는
    비활성 provider(예: ACE-Step)도 활성 provider(Suno)와 같은 입력으로 돌려
    결과를 비교해야 하기 때문이다."""
    db = SessionLocal()
    try:
        rows = (
            db.query(Provider)
            .filter(Provider.step == step)
            .order_by(Provider.id)
            .all()
        )
        return [(row.name, load_provider(row.class_path)) for row in rows]
    finally:
        db.close()
