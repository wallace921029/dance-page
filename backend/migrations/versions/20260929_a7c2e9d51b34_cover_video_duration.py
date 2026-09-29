"""cover video duration

Revision ID: a7c2e9d51b34
Revises: d4e6b1a9c3f7
Create Date: 2026-09-29 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c2e9d51b34"
down_revision: str | Sequence[str] | None = "d4e6b1a9c3f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 封面动画生成时用的时长（秒）：生成时可以临时指定时长和清晰度（D79），
    # 判断"需要重新生成"时按生成时的参数比较
    with op.batch_alter_table("books", schema=None) as batch_op:
        batch_op.add_column(sa.Column("cover_video_duration_s", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("books", schema=None) as batch_op:
        batch_op.drop_column("cover_video_duration_s")
