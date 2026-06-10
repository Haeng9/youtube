"""DB의 providers 테이블 설정을 읽어 provider 클래스를 동적으로 로딩한다."""
import importlib
from typing import Optional

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
