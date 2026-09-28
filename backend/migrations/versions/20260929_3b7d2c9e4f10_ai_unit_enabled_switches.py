"""ai unit enabled switches

Revision ID: 3b7d2c9e4f10
Revises: 124af3260e26
Create Date: 2026-09-29 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3b7d2c9e4f10"
down_revision: str | Sequence[str] | None = "124af3260e26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 开页的"朗读""动画"开关（D95），已有单元默认打开
    with op.batch_alter_table("ai_units", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("audio_enabled", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(
            sa.Column("video_enabled", sa.Boolean(), nullable=False, server_default=sa.true())
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("ai_units", schema=None) as batch_op:
        batch_op.drop_column("video_enabled")
        batch_op.drop_column("audio_enabled")
