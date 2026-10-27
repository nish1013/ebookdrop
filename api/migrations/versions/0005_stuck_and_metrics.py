"""stuck books and the metric report views

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"

_FAILURES = "'malformed', 'unreadable', 'timed_out', 'crashed'"

# Days are UTC days of `UploadReceived`. A book counts once, at its first event.
_READY_TIMES = """
CREATE VIEW metric_ready_times AS
WITH received AS (
    SELECT book_id, min(at) AS at FROM book_events
    WHERE name = 'upload_received' GROUP BY book_id
), ready AS (
    SELECT book_id, min(at) AS at FROM book_events
    WHERE name = 'book_ready' GROUP BY book_id
)
SELECT received.book_id,
       (received.at AT TIME ZONE 'UTC')::date AS day,
       received.at AS received_at,
       ready.at AS ready_at,
       ready.at - received.at <= interval '2 minutes' AS in_time
FROM received LEFT JOIN ready ON ready.book_id = received.book_id
"""

# A book counts one open failure per UTC day, so a retry loop cannot inflate it.
_DAILY_SHARE = """
CREATE VIEW metric_daily_share AS
WITH shares AS (
    SELECT day, count(*) AS received, count(*) FILTER (WHERE in_time) AS in_time
    FROM metric_ready_times GROUP BY day
), open_failures AS (
    SELECT (at AT TIME ZONE 'UTC')::date AS day,
           count(DISTINCT book_id) AS open_failures
    FROM book_events WHERE name = 'book_open_failed' GROUP BY 1
)
SELECT coalesce(shares.day, open_failures.day) AS day,
       coalesce(shares.received, 0) AS received,
       coalesce(shares.in_time, 0) AS ready_in_time,
       round(100.0 * shares.in_time / nullif(shares.received, 0), 1)
           AS share_percent,
       coalesce(open_failures.open_failures, 0) AS open_failures
FROM shares FULL JOIN open_failures ON open_failures.day = shares.day
"""

_LATE_BOOKS = """
CREATE VIEW metric_late_books AS
SELECT book_id, received_at, ready_at FROM metric_ready_times
WHERE NOT in_time
"""

_REJECTS = """
CREATE VIEW metric_rejects AS
SELECT (at AT TIME ZONE 'UTC')::date AS day, reason, count(*) AS count
FROM intake_events WHERE name = 'upload_rejected' GROUP BY 1, 2
"""


def upgrade() -> None:
    op.drop_constraint("books_failure", "books")
    op.create_check_constraint(
        "books_failure", "books", f"failure IN ({_FAILURES}, 'stuck')"
    )
    for view in (_READY_TIMES, _DAILY_SHARE, _LATE_BOOKS, _REJECTS):
        op.execute(view)


def downgrade() -> None:
    for view in ("metric_rejects", "metric_late_books", "metric_daily_share"):
        op.execute(f"DROP VIEW {view}")
    op.execute("DROP VIEW metric_ready_times")
    op.drop_constraint("books_failure", "books")
    op.create_check_constraint("books_failure", "books", f"failure IN ({_FAILURES})")
