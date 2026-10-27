"""Serve the API on a fresh Postgres container for browser tests and local runs."""

import os

import uvicorn
from alembic import command
from alembic.config import Config
from testcontainers.community.postgres import PostgresContainer

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with PostgresContainer("postgres:16-alpine", driver="psycopg") as postgres:
    os.environ["DATABASE_URL"] = postgres.get_connection_url()
    config = Config(os.path.join(HERE, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(HERE, "migrations"))
    command.upgrade(config, "head")
    uvicorn.run("ebookdrop.app:app_from_env", factory=True, host="127.0.0.1", port=8000)
