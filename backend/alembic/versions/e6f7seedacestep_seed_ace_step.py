"""seed ace_step music provider (inactive, coexists with suno)

Revision ID: e6f7seedacestep
Revises: d5e6activatesuno
Create Date: 2026-06-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e6f7seedacestep"
down_revision: Union[str, Sequence[str], None] = "d5e6activatesuno"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_providers = sa.table(
    "providers",
    sa.column("step", sa.String),
    sa.column("name", sa.String),
    sa.column("class_path", sa.String),
    sa.column("is_active", sa.Boolean),
)

_ACE_STEP = {
    "step": "music",
    "name": "ace_step",
    "class_path": "app.pipeline.providers.ace_step_provider.AceStepProvider",
    "is_active": False,
}


def upgrade() -> None:
    # ACE-Step를 music provider로 등록하되 비활성(coexist) — active는 suno 유지.
    op.bulk_insert(_providers, [_ACE_STEP])


def downgrade() -> None:
    op.execute(_providers.delete().where(_providers.c.name == "ace_step"))
