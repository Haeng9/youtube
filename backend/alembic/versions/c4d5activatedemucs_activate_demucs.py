"""activate demucs separation provider, deactivate stub_separation

Revision ID: c4d5activatedemucs
Revises: b1c3seedproviders
Create Date: 2026-06-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4d5activatedemucs"
down_revision: Union[str, Sequence[str], None] = "b1c3seedproviders"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_providers = sa.table(
    "providers",
    sa.column("step", sa.String),
    sa.column("name", sa.String),
    sa.column("class_path", sa.String),
    sa.column("is_active", sa.Boolean),
)

_DEMUCS = {
    "step": "separation",
    "name": "demucs",
    "class_path": "app.pipeline.providers.demucs_provider.DemucsProvider",
    "is_active": True,
}


def upgrade() -> None:
    # stub을 비활성화하고 demucs를 활성 separation provider로 등록
    op.execute(
        _providers.update()
        .where(_providers.c.name == "stub_separation")
        .values(is_active=False)
    )
    op.bulk_insert(_providers, [_DEMUCS])


def downgrade() -> None:
    op.execute(_providers.delete().where(_providers.c.name == "demucs"))
    op.execute(
        _providers.update()
        .where(_providers.c.name == "stub_separation")
        .values(is_active=True)
    )
