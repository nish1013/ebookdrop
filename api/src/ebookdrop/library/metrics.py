"""The metric report: reads the metric views of the library (decisions 12, 14, 15)."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Engine, text


@dataclass(frozen=True)
class DailyShare:
    """One day of received uploads, by the UTC day of `UploadReceived`."""

    day: date
    received: int
    ready_in_time: int
    share_percent: Decimal | None
    open_failures: int


@dataclass(frozen=True)
class LateBook:
    """A book that became ready more than 2 minutes after `UploadReceived`."""

    book_id: uuid.UUID
    received_at: datetime
    ready_at: datetime


@dataclass(frozen=True)
class RejectCount:
    """The rejected uploads of one day with one reason."""

    day: date
    reason: str
    count: int


@dataclass(frozen=True)
class MetricReport:
    """The daily share, the late books and the rejects by reason."""

    days: list[DailyShare]
    late: list[LateBook]
    rejects: list[RejectCount]


class MetricReader:
    """Reads the metric report from its views."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def report(self) -> MetricReport:
        """Return the whole report, oldest day first."""
        with self._engine.connect() as connection:
            days = connection.execute(_DAYS).all()
            late = connection.execute(_LATE).all()
            rejects = connection.execute(_REJECTS).all()
        return MetricReport(
            [DailyShare(*row) for row in days],
            [LateBook(*row) for row in late],
            [RejectCount(*row) for row in rejects],
        )


_DAYS = text(
    "SELECT day, received, ready_in_time, share_percent, open_failures"
    " FROM metric_daily_share ORDER BY day"
)
_LATE = text(
    "SELECT book_id, received_at, ready_at FROM metric_late_books"
    " ORDER BY received_at, book_id"
)
_REJECTS = text("SELECT day, reason, count FROM metric_rejects ORDER BY day, reason")
