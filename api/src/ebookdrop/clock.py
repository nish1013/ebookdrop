"""The time source, behind a port so tests can move it."""

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Gives the current time as a zone-aware UTC datetime."""

    def now(self) -> datetime: ...


class SystemClock:
    """The real clock."""

    def now(self) -> datetime:
        return datetime.now(UTC)
