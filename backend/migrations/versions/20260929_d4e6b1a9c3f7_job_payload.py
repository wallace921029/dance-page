"""job payload

Revision ID: d4e6b1a9c3f7
Revises: 8c1f4a7d2e55
Create Date: 2026-09-29 02:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e6b1a9c3f7"
down_revision: str | Sequence[str] | None = "8c1f4a7d2e55"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 任务参数（如视频任务提交时用的服务商、模型、指纹），查询和完成时使用（D96）
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("payload", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_column("payload")
