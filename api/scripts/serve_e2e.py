"""Serve the API and the worker on a fresh Postgres for browser tests and local runs."""

import os
import tempfile
import threading

import uvicorn
from alembic import command
from alembic.config import Config
from testcontainers.community.postgres import PostgresContainer

from ebookdrop.worker import worker_from_env

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with (
    PostgresContainer("postgres:16-alpine", driver="psycopg") as postgres,
    tempfile.TemporaryDirectory() as storage_dir,
):
    os.environ["DATABASE_URL"] = postgres.get_connection_url()
    os.environ["STORAGE_DIR"] = storage_dir
    config = Config(os.path.join(HERE, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(HERE, "migrations"))
    command.upgrade(config, "head")
    stop = threading.Event()
    threading.Thread(
        target=worker_from_env().run_until, args=(stop,), daemon=True
    ).start()
    uvicorn.run("ebookdrop.app:app_from_env", factory=True, host="127.0.0.1", port=8000)
    stop.set()
