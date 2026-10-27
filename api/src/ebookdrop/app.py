"""The web application and its wiring."""

import os
from pathlib import Path

from fastapi import FastAPI, Request, status
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
from ebookdrop.library.service import LibraryService
from ebookdrop.library.store import LibraryStore
from ebookdrop.storage import LocalDiskStorage, StoragePort


def create_app(
    engine: Engine, clock: Clock, storage: StoragePort, inspector: InspectorPort
) -> FastAPI:
    """Build the API on one database, one clock, one storage and one inspector."""
    app = FastAPI(title="ebookdrop")
    app.add_exception_handler(RequestValidationError, _refuse_body)
    identity = IdentityService(IdentityStore(engine), clock)
    add_identity(app, identity)
    library = LibraryService(LibraryStore(engine), storage, clock, inspector)
    add_library(app, library, signed_in_reader(identity))
    return app


def conversion_jobs(
    engine: Engine, clock: Clock, storage: StoragePort, converter: ConverterPort
) -> ConversionJobs:
    """Build the P1 poller on the same parts as the API."""
    return ConversionJobs(LibraryStore(engine), storage, converter, clock)


def file_removal(engine: Engine, clock: Clock, storage: StoragePort) -> FileRemoval:
    """Build P4, P5 and the staging sweep on the same parts as the API."""
    return FileRemoval(LibraryStore(engine), storage, clock)


def storage_from_env() -> StoragePort:
    """Build the storage from `STORAGE_DIR`."""
    return LocalDiskStorage(Path(os.environ["STORAGE_DIR"]))


def app_from_env() -> FastAPI:
    """Build the API from `DATABASE_URL` and `STORAGE_DIR`, for uvicorn `--factory`."""
    engine = create_engine(os.environ["DATABASE_URL"])
    return create_app(engine, SystemClock(), storage_from_env(), DockerInspector())


async def _refuse_body(_: Request, __: Exception) -> JSONResponse:
    return JSONResponse(
        {"code": "invalid_request"},
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )
