"""The web application and its wiring."""

import os

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, create_engine

from ebookdrop.clock import Clock, SystemClock
from ebookdrop.identity.http import add_identity
from ebookdrop.identity.service import IdentityService
from ebookdrop.identity.store import IdentityStore


def create_app(engine: Engine, clock: Clock) -> FastAPI:
    """Build the API on one database and one clock."""
    app = FastAPI(title="ebookdrop")
    app.add_exception_handler(RequestValidationError, _refuse_body)
    add_identity(app, IdentityService(IdentityStore(engine), clock))
    return app


def app_from_env() -> FastAPI:
    """Build the API from `DATABASE_URL`, for uvicorn `--factory`."""
    return create_app(create_engine(os.environ["DATABASE_URL"]), SystemClock())


async def _refuse_body(_: Request, __: Exception) -> JSONResponse:
    return JSONResponse(
        {"code": "invalid_request"},
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )
