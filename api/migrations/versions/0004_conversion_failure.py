"""conversion failure: the reason a book failed

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade() -> None:
    op.add_column("books", sa.Column("failure", sa.Text))
    op.create_check_constraint(
        "books_failure",
        "books",
        "failure IN ('malformed', 'unreadable', 'timed_out', 'crashed')",
    )


def downgrade() -> None:
    op.drop_constraint("books_failure", "books")
    op.drop_column("books", "failure")
