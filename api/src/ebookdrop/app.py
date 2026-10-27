"""The web application and its wiring."""

import os

from fastapi import FastAPI
from sqlalchemy import Engine, create_engine

from ebookdrop.clock import Clock, SystemClock
from ebookdrop.identity.http import add_identity
from ebookdrop.identity.service import IdentityService
from ebookdrop.identity.store import IdentityStore


def create_app(engine: Engine, clock: Clock) -> FastAPI:
    """Build the API on one database and one clock."""
    app = FastAPI(title="ebookdrop")
    add_identity(app, IdentityService(IdentityStore(engine), clock))
    return app


def app_from_env() -> FastAPI:
    """Build the API from `DATABASE_URL`, for uvicorn `--factory`."""
    return create_app(create_engine(os.environ["DATABASE_URL"]), SystemClock())
