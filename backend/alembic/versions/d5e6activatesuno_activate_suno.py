"""activate suno music provider, deactivate stub_music

Revision ID: d5e6activatesuno
Revises: c4d5activatedemucs
Create Date: 2026-06-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d5e6activatesuno"
down_revision: Union[str, Sequence[str], None] = "c4d5activatedemucs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_providers = sa.table(
    "providers",
    sa.column("step", sa.String),
    sa.column("name", sa.String),
    sa.column("class_path", sa.String),
    sa.column("is_active", sa.Boolean),
)

_SUNO = {
    "step": "music",
    "name": "suno",
    "class_path": "app.pipeline.providers.suno_provider.SunoProvider",
    "is_active": True,
}


def upgrade() -> None:
    # stub_music을 비활성화하고 suno를 활성 music provider로 등록
    op.execute(
        _providers.update()
        .where(_providers.c.name == "stub_music")
        .values(is_active=False)
    )
    op.bulk_insert(_providers, [_SUNO])


def downgrade() -> None:
    op.execute(_providers.delete().where(_providers.c.name == "suno"))
    op.execute(
        _providers.update()
        .where(_providers.c.name == "stub_music")
        .values(is_active=True)
    )
