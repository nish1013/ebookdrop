"""Serve the API and the worker on a fresh Postgres for browser tests and local runs."""

import os
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from testcontainers.community.postgres import PostgresContainer

from ebookdrop.app import conversion_jobs
from ebookdrop.clock import SystemClock
from ebookdrop.conversion.port import Conversion
from ebookdrop.conversion.stub import StubConverter
from ebookdrop.storage import LocalDiskStorage
from ebookdrop.worker import run_until

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONVERT_SECONDS = 2.0


class SlowStubConverter(StubConverter):
    """Holds each book in Processing long enough for a page to show it."""

    def convert(self, source: Path, work_dir: Path) -> Conversion:
        time.sleep(CONVERT_SECONDS)
        return super().convert(source, work_dir)


with (
    PostgresContainer("postgres:16-alpine", driver="psycopg") as postgres,
    tempfile.TemporaryDirectory() as storage_dir,
):
    os.environ["DATABASE_URL"] = postgres.get_connection_url()
    os.environ["STORAGE_DIR"] = storage_dir
    config = Config(os.path.join(HERE, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(HERE, "migrations"))
    command.upgrade(config, "head")
    jobs = conversion_jobs(
        create_engine(os.environ["DATABASE_URL"]),
        SystemClock(),
        LocalDiskStorage(Path(storage_dir)),
        SlowStubConverter(),
    )
    stop = threading.Event()
    threading.Thread(target=run_until, args=(stop, jobs), daemon=True).start()
    uvicorn.run("ebookdrop.app:app_from_env", factory=True, host="127.0.0.1", port=8000)
    stop.set()
