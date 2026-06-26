"""seed ffmpeg_synthesis synthesis provider (active)

Revision ID: h9i0seedffmpeg
Revises: g8h9activateltx
Create Date: 2026-06-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "h9i0seedffmpeg"
down_revision: Union[str, Sequence[str], None] = "g8h9activateltx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_providers = sa.table(
    "providers",
    sa.column("step", sa.String),
    sa.column("name", sa.String),
    sa.column("class_path", sa.String),
    sa.column("is_active", sa.Boolean),
)

_FFMPEG = {
    "step": "synthesis",
    "name": "ffmpeg_synthesis",
    "class_path": "app.pipeline.providers.ffmpeg_synthesis_provider.FfmpegSynthesisProvider",
    "is_active": True,
}


def upgrade() -> None:
    # synthesis step은 기존 시드(b1c3)에 없던 신규 step — stub 없이 바로 active 등록.
    # (결정적 합성이라 옵션이 ffmpeg 하나뿐, stub 불필요.)
    op.bulk_insert(_providers, [_FFMPEG])


def downgrade() -> None:
    op.execute(_providers.delete().where(_providers.c.name == "ffmpeg_synthesis"))
