"""The web application and its wiring."""

import os
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, create_engine

from ebookdrop.clock import Clock, SystemClock
from ebookdrop.conversion.port import ConverterPort
from ebookdrop.identity.http import add_identity, signed_in_reader
from ebookdrop.identity.service import IdentityService
from ebookdrop.identity.store import IdentityStore
from ebookdrop.inspection.docker import DockerInspector
from ebookdrop.inspection.port import InspectorPort
from ebookdrop.library.conversion_jobs import ConversionJobs
from ebookdrop.library.file_removal import FileRemoval
from ebookdrop.library.http import add_library
from ebookdrop.library.library_removal import LibraryRemoval
from ebookdrop.library.service import LibraryService
from ebookdrop.library.store import LibraryStore
from ebookdrop.storage import LocalDiskStorage, StoragePort

_Handler = Callable[[Request], Awaitable[Response]]
_Middleware = Callable[[Request, _Handler], Awaitable[Response]]

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def create_app(
    engine: Engine,
    clock: Clock,
    storage: StoragePort,
    inspector: InspectorPort,
    *,
    origin: str,
) -> FastAPI:
    """Build the API on one database, one clock, one storage and one inspector.

    A POST, PUT or DELETE from a page outside `origin` is refused.
    """
    app = FastAPI(title="ebookdrop")
    app.add_exception_handler(RequestValidationError, _refuse_body)
    app.middleware("http")(_cross_origin_refusal(origin.rstrip("/")))
    identity = identity_service(engine, clock)
    add_identity(app, identity)
    library = LibraryService(LibraryStore(engine), storage, clock, inspector)
    add_library(app, library, signed_in_reader(identity))
    return app


def identity_service(engine: Engine, clock: Clock) -> IdentityService:
    """Build the identity commands on the same parts as the API."""
    return IdentityService(IdentityStore(engine), clock)


def conversion_jobs(
    engine: Engine, clock: Clock, storage: StoragePort, converter: ConverterPort
) -> ConversionJobs:
    """Build the P1 poller on the same parts as the API."""
    return ConversionJobs(LibraryStore(engine), storage, converter, clock)


def file_removal(engine: Engine, clock: Clock, storage: StoragePort) -> FileRemoval:
    """Build P4, P5 and the staging sweep on the same parts as the API."""
    return FileRemoval(LibraryStore(engine), storage, clock)


def library_removal(engine: Engine, clock: Clock) -> LibraryRemoval:
    """Build P6 on the same parts as the API."""
    return LibraryRemoval(LibraryStore(engine), clock)


def storage_from_env() -> StoragePort:
    """Build the storage from `STORAGE_DIR`."""
    return LocalDiskStorage(Path(os.environ["STORAGE_DIR"]))


def app_from_env() -> FastAPI:
    """Build the API from `DATABASE_URL`, `STORAGE_DIR` and `APP_ORIGIN`.

    For uvicorn `--factory`. `APP_ORIGIN` is the scheme, host and port of the web
    page, as the browser shows it.
    """
    engine = create_engine(os.environ["DATABASE_URL"])
    return create_app(
        engine,
        SystemClock(),
        storage_from_env(),
        DockerInspector(),
        origin=os.environ["APP_ORIGIN"],
    )


async def _refuse_body(_: Request, __: Exception) -> JSONResponse:
    return JSONResponse(
        {"code": "invalid_request"},
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )


def _cross_origin_refusal(origin: str) -> _Middleware:
    # SameSite=Lax still sends the cookie from a sibling subdomain. Browsers send
    # Origin on each cross-origin POST, PUT and DELETE, so no Origin passes. A
    # proxy can rewrite Host, so the page origin is set, not taken from Host.
    async def refuse(request: Request, call_next: _Handler) -> Response:
        sent = request.headers.get("origin")
        if request.method in _SAFE_METHODS or sent is None or sent == origin:
            return await call_next(request)
        return JSONResponse(
            {"code": "cross_origin"}, status_code=status.HTTP_403_FORBIDDEN
        )

    return refuse
