"""activate ltx_video video provider, deactivate stub_video

Revision ID: g8h9activateltx
Revises: f7g8activatesdxl
Create Date: 2026-06-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "g8h9activateltx"
down_revision: Union[str, Sequence[str], None] = "f7g8activatesdxl"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_providers = sa.table(
    "providers",
    sa.column("step", sa.String),
    sa.column("name", sa.String),
    sa.column("class_path", sa.String),
    sa.column("is_active", sa.Boolean),
)

_LTX = {
    "step": "video",
    "name": "ltx_video",
    "class_path": "app.pipeline.providers.ltx_video_provider.LtxVideoProvider",
    "is_active": True,
}


def upgrade() -> None:
    # stub_video를 비활성화하고 ltx_video를 활성 video provider로 등록 (Demucs/Suno/SDXL 패턴).
    op.execute(
        _providers.update()
        .where(_providers.c.name == "stub_video")
        .values(is_active=False)
    )
    op.bulk_insert(_providers, [_LTX])


def downgrade() -> None:
    op.execute(_providers.delete().where(_providers.c.name == "ltx_video"))
    op.execute(
        _providers.update()
        .where(_providers.c.name == "stub_video")
        .values(is_active=True)
    )
