"""The worker process: polls the conversion outbox (P1)."""

import logging
import os
import threading

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

from ebookdrop.app import conversion_jobs, storage_from_env
from ebookdrop.clock import SystemClock
from ebookdrop.conversion.docker import DockerConverter
from ebookdrop.conversion.port import ConverterUnavailableError
from ebookdrop.library.conversion_jobs import ConversionJobs

POLL_SECONDS = 1.0

_log = logging.getLogger(__name__)


def run_until(stop: threading.Event, jobs: ConversionJobs) -> None:
    """Poll the outbox until `stop` is set. A failed poll waits for the next one."""
    while not stop.is_set():
        try:
            taken = jobs.poll()
        except (OSError, SQLAlchemyError, ConverterUnavailableError):
            _log.exception("conversion poll failed")
            taken = 0
        if not taken:
            stop.wait(POLL_SECONDS)


def main() -> None:
    """Run the worker on `DATABASE_URL` and `STORAGE_DIR`."""
    logging.basicConfig(level=logging.INFO)
    engine = create_engine(os.environ["DATABASE_URL"])
    jobs = conversion_jobs(engine, SystemClock(), storage_from_env(), DockerConverter())
    run_until(threading.Event(), jobs)


if __name__ == "__main__":
    main()
