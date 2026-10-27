"""The worker process: polls the conversion outbox (P1)."""

import logging
import os
import threading
from typing import Protocol

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from ebookdrop.app import conversion_jobs, storage_from_env
from ebookdrop.clock import SystemClock
from ebookdrop.conversion.docker import DockerConverter
from ebookdrop.conversion.port import ConverterUnavailableError

POLL_SECONDS = 1.0

_log = logging.getLogger(__name__)


class Jobs(Protocol):
    """The library steps the worker runs."""

    def poll(self) -> int: ...


class Worker:
    """Runs the library steps in one process."""

    def __init__(self, jobs: Jobs) -> None:
        self._jobs = jobs

    def tick(self) -> int:
        """Run one poll. Return how many jobs it took."""
        return self._jobs.poll()

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
    jobs = conversion_jobs(engine, SystemClock(), storage_from_env(), DockerConverter())
    Worker(jobs).run_until(threading.Event())


if __name__ == "__main__":
    main()
