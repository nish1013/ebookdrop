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
    identity_service,
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


class Failures(Protocol):
    """The sign-in failure cleanup the worker runs once a day."""

    def forget_old_failures(self) -> int: ...


class Worker:
    """Runs the library steps in one process."""

    def __init__(
        self,
        jobs: Jobs,
        removals: Removals,
        libraries: Libraries,
        failures: Failures,
        clock: Clock,
    ) -> None:
        self._jobs = jobs
        self._removals = removals
        self._libraries = libraries
        self._failures = failures
        self._clock = clock
        self._next_stuck_check: datetime | None = None
        self._next_cleanup: datetime | None = None

    def tick(self) -> int:
        """Run the stuck check (P2) and the daily cleanup when due, then the polls.

        The daily cleanup is P5, the staging sweep and the sign-in failures past
        their window, each in its own guard, so
        one failure waits a day and stops nothing else. P6 runs before P4, so
        the files of a removed library go in the same tick. Return how many
        libraries (P6), file removals (P4) and jobs the polls took.
        """
        now = self._clock.now()
        if self._next_stuck_check is None or now >= self._next_stuck_check:
            self._next_stuck_check = now + STUCK_CHECK_EVERY
            self._jobs.fail_stuck()
        if self._next_cleanup is None or now >= self._next_cleanup:
            self._next_cleanup = now + CLEANUP_EVERY
            _guarded(self._removals.clean_failed)
            _guarded(self._removals.sweep_staging)
            _guarded(self._failures.forget_old_failures)
        libraries = self._libraries.poll()
        return libraries + self._removals.poll() + self._jobs.poll()

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


def worker_from_env() -> Worker:
    """Build the worker on `DATABASE_URL` and `STORAGE_DIR`."""
    engine = create_engine(os.environ["DATABASE_URL"])
    clock = SystemClock()
    storage = storage_from_env()
    jobs = conversion_jobs(engine, clock, storage, DockerConverter())
    removals = file_removal(engine, clock, storage)
    libraries = library_removal(engine, clock)
    failures = identity_service(engine, clock)
    return Worker(jobs, removals, libraries, failures, clock)


def main() -> None:
    """Run the worker on `DATABASE_URL` and `STORAGE_DIR`."""
    logging.basicConfig(level=logging.INFO)
    worker_from_env().run_until(threading.Event())


def _guarded(step: Callable[[], int]) -> None:
    try:
        step()
    except (OSError, SQLAlchemyError):
        _log.exception("worker clean-up step failed")


if __name__ == "__main__":
    main()
