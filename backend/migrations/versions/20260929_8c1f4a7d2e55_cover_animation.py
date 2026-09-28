"""cover animation

Revision ID: 8c1f4a7d2e55
Revises: 3b7d2c9e4f10
Create Date: 2026-09-29 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.db  # noqa: F401  自定义列类型 UTCDateTime

# revision identifiers, used by Alembic.
revision: str = "8c1f4a7d2e55"
down_revision: str | Sequence[str] | None = "3b7d2c9e4f10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 封面动画（D96）
    with op.batch_alter_table("books", schema=None) as batch_op:
        batch_op.add_column(sa.Column("cover_motion_prompt", sa.String(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "cover_video_status", sa.String(length=16), nullable=False, server_default="none"
            )
        )
        batch_op.add_column(sa.Column("cover_video_error", sa.String(), nullable=True))
        batch_op.add_column(
            sa.Column("cover_video_version", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("cover_video_source_hash", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("cover_video_frame", sa.String(length=32), nullable=True))
        batch_op.add_column(
            sa.Column("cover_video_resolution", sa.String(length=16), nullable=True)
        )
        batch_op.add_column(
            sa.Column("cover_video_enabled_at", app.db.UTCDateTime(), nullable=True)
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("books", schema=None) as batch_op:
        batch_op.drop_column("cover_video_enabled_at")
        batch_op.drop_column("cover_video_resolution")
        batch_op.drop_column("cover_video_frame")
        batch_op.drop_column("cover_video_source_hash")
        batch_op.drop_column("cover_video_version")
        batch_op.drop_column("cover_video_error")
        batch_op.drop_column("cover_video_status")
        batch_op.drop_column("cover_motion_prompt")
