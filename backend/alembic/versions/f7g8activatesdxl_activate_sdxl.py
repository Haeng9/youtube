"""activate sdxl image provider, deactivate stub_image

Revision ID: f7g8activatesdxl
Revises: e6f7seedacestep
Create Date: 2026-06-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f7g8activatesdxl"
down_revision: Union[str, Sequence[str], None] = "e6f7seedacestep"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_providers = sa.table(
    "providers",
    sa.column("step", sa.String),
    sa.column("name", sa.String),
    sa.column("class_path", sa.String),
    sa.column("is_active", sa.Boolean),
)

_SDXL = {
    "step": "image",
    "name": "sdxl",
    "class_path": "app.pipeline.providers.sdxl_provider.SdxlProvider",
    "is_active": True,
}


def upgrade() -> None:
    # stub_image를 비활성화하고 sdxl을 활성 image provider로 등록 (Demucs/Suno 패턴).
    op.execute(
        _providers.update()
        .where(_providers.c.name == "stub_image")
        .values(is_active=False)
    )
    op.bulk_insert(_providers, [_SDXL])


def downgrade() -> None:
    op.execute(_providers.delete().where(_providers.c.name == "sdxl"))
    op.execute(
        _providers.update()
        .where(_providers.c.name == "stub_image")
        .values(is_active=True)
    )
