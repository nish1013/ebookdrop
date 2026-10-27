"""The worker process: the conversion outbox (P1), the stuck check (P2), P4 to P6."""

import logging
import os
import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Protocol

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from ebookdrop.app import (
    conversion_jobs,
    file_removal,
    library_removal,
    storage_from_env,
)
from ebookdrop.clock import Clock, SystemClock
from ebookdrop.conversion.docker import DockerConverter
from ebookdrop.conversion.port import ConverterUnavailableError

POLL_SECONDS = 1.0
STUCK_CHECK_EVERY = timedelta(minutes=1)
CLEANUP_EVERY = timedelta(days=1)

_log = logging.getLogger(__name__)


class Jobs(Protocol):
    """The library steps the worker runs."""

    def poll(self) -> int: ...

    def fail_stuck(self) -> int: ...


class Removals(Protocol):
    """The file removal steps the worker runs."""

    def poll(self) -> int: ...

    def clean_failed(self) -> int: ...

    def sweep_staging(self) -> int: ...


class Libraries(Protocol):
    """The library removal step (P6) the worker runs."""

    def poll(self) -> int: ...


class Worker:
    """Runs the library steps in one process."""

    def __init__(
        self, jobs: Jobs, removals: Removals, libraries: Libraries, clock: Clock
    ) -> None:
        self._jobs = jobs
        self._removals = removals
        self._libraries = libraries
        self._clock = clock
        self._next_stuck_check: datetime | None = None
        self._next_cleanup: datetime | None = None

    def tick(self) -> int:
        """Run the stuck check (P2) and the daily cleanup when due, then the polls.

        The daily cleanup is P5 and the staging sweep, each in its own guard, so
        one failure waits a day and stops nothing else. Return how many jobs and
        file removals (P4) the polls took.
        """
        now = self._clock.now()
        if self._next_stuck_check is None or now >= self._next_stuck_check:
            self._next_stuck_check = now + STUCK_CHECK_EVERY
            self._jobs.fail_stuck()
        if self._next_cleanup is None or now >= self._next_cleanup:
            self._next_cleanup = now + CLEANUP_EVERY
            _guarded(self._removals.clean_failed)
            _guarded(self._removals.sweep_staging)
        return self._removals.poll() + self._jobs.poll()

    def run_until(self, stop: threading.Event) -> None:
        """Tick until `stop` is set. A failed tick waits for the next one."""
        while not stop.is_set():
            try:
                taken = self.tick()
            except (OSError, SQLAlchemyError, ConverterUnavailableError):
                _log.exception("worker tick failed")
                taken = 0
            if not taken:
                stop.wait(POLL_SECONDS)


def main() -> None:
    """Run the worker on `DATABASE_URL` and `STORAGE_DIR`."""
    logging.basicConfig(level=logging.INFO)
    engine = create_engine(os.environ["DATABASE_URL"])
    clock = SystemClock()
    storage = storage_from_env()
    jobs = conversion_jobs(engine, clock, storage, DockerConverter())
    removals = file_removal(engine, clock, storage)
    libraries = library_removal(engine, clock)
    Worker(jobs, removals, libraries, clock).run_until(threading.Event())


def _guarded(step: Callable[[], int]) -> None:
    try:
        step()
    except (OSError, SQLAlchemyError):
        _log.exception("worker clean-up step failed")


if __name__ == "__main__":
    main()
