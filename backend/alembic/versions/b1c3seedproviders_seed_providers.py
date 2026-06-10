"""seed providers (stub one per step)

Revision ID: b1c3seedproviders
Revises: ab26825db0cf
Create Date: 2026-06-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1c3seedproviders"
down_revision: Union[str, Sequence[str], None] = "ab26825db0cf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# lightweight ad-hoc table for data-only insert/delete
_providers = sa.table(
    "providers",
    sa.column("step", sa.String),
    sa.column("name", sa.String),
    sa.column("class_path", sa.String),
    sa.column("is_active", sa.Boolean),
)

_SEED = [
    {"step": "separation", "name": "stub_separation",
     "class_path": "app.pipeline.providers.stubs.StubSeparationProvider", "is_active": True},
    {"step": "music", "name": "stub_music",
     "class_path": "app.pipeline.providers.stubs.StubMusicProvider", "is_active": True},
    {"step": "image", "name": "stub_image",
     "class_path": "app.pipeline.providers.stubs.StubImageProvider", "is_active": True},
    {"step": "video", "name": "stub_video",
     "class_path": "app.pipeline.providers.stubs.StubVideoProvider", "is_active": True},
]


def upgrade() -> None:
    op.bulk_insert(_providers, _SEED)


def downgrade() -> None:
    names = [row["name"] for row in _SEED]
    op.execute(
        _providers.delete().where(_providers.c.name.in_(names))
    )
