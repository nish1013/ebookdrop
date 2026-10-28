"""file removals: the P4 outbox

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0006"
down_revision = "0005"


def upgrade() -> None:
    # No foreign key: the book row is gone when its removal waits.
    op.create_table(
        "file_removals",
        sa.Column("book_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("format", sa.Text),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("format IN ('epub', 'pdf')", name="file_removals_format"),
    )
    op.create_index("file_removals_queued", "file_removals", ["queued_at"])


def downgrade() -> None:
    op.drop_table("file_removals")
