"""Library endpoints."""

import tempfile
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Annotated, BinaryIO

from fastapi import APIRouter, Depends, FastAPI, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel
from starlette.requests import ClientDisconnect

from ebookdrop.conversion.port import BookFormat, Failure
from ebookdrop.identity.domain import SignedInReader
from ebookdrop.identity.http import ErrorOut
from ebookdrop.library.domain import (
    Book,
    BookNotFoundError,
    BookStatus,
    DuplicateUploadError,
    InspectUnavailableError,
    InvalidFileNameError,
    InvalidUploadError,
    LibraryError,
    ReaderGoneError,
    RejectReason,
    UploadAbandonedError,
    UploadRejectedError,
)
from ebookdrop.library.service import LibraryService
from ebookdrop.library.upload_stream import declared_too_large, receive_upload

_ANSWERS: dict[type[LibraryError], tuple[int, str]] = {
    InvalidFileNameError: (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "invalid_file_name",
    ),
    InvalidUploadError: (status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_request"),
    UploadAbandonedError: (status.HTTP_400_BAD_REQUEST, "upload_abandoned"),
    InspectUnavailableError: (
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "inspect_unavailable",
    ),
    BookNotFoundError: (status.HTTP_404_NOT_FOUND, "book_not_found"),
    ReaderGoneError: (status.HTTP_401_UNAUTHORIZED, "signed_out"),
}
_MEDIA_TYPES = {
    BookFormat.EPUB: "application/epub+zip",
    BookFormat.PDF: "application/pdf",
}
_BOOK_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; script-src 'none'; sandbox",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "private, no-store",
}
_CHUNK = 64 * 1024
_FILE_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["file"],
                    "properties": {"file": {"type": "string", "format": "binary"}},
                }
            }
        },
    }
}


class DuplicateOut(BaseModel):
    """The reject of a file the reader already owns, with a link to that book."""

    code: str
    book_id: uuid.UUID
    title: str


class BookOut(BaseModel):
    """A book as the library list shows it."""

    id: uuid.UUID
    title: str
    author: str | None
    status: BookStatus
    cover_url: str | None
    failure: Failure | None


def add_library(
    app: FastAPI,
    service: LibraryService,
    signed_in: Callable[..., SignedInReader],
) -> None:
    """Add the library endpoints and their error answers to the app."""
    router = APIRouter(
        prefix="/api", responses={401: {"model": ErrorOut}, 422: {"model": ErrorOut}}
    )
    Reader = Annotated[SignedInReader, Depends(signed_in)]

    @router.post(
        "/books",
        status_code=status.HTTP_201_CREATED,
        openapi_extra=_FILE_BODY,
        responses={
            409: {"model": DuplicateOut},
            413: {"model": ErrorOut},
            503: {"model": ErrorOut},
        },
    )
    async def upload_book(reader: Reader, request: Request) -> BookOut:
        if declared_too_large(request):
            raise await run_in_threadpool(
                service.reject, reader.id, RejectReason.TOO_LARGE
            )
        with tempfile.TemporaryDirectory() as work:
            try:
                received = await receive_upload(request, Path(work))
            except UploadRejectedError as rejected:
                raise await run_in_threadpool(
                    service.reject, reader.id, rejected.reason
                ) from None
            except ClientDisconnect:
                await run_in_threadpool(service.abandon, reader.id)
                raise UploadAbandonedError from None
            book = await run_in_threadpool(service.upload, reader.id, received)
        return _out(book)

    @router.get("/books")
    def list_books(reader: Reader) -> list[BookOut]:
        return [_out(book) for book in service.books(reader.id)]

    @router.get(
        "/books/{book_id}/cover",
        response_class=Response,
        responses={
            200: {"content": {"image/png": {}}},
            404: {"model": ErrorOut},
        },
    )
    def book_cover(reader: Reader, book_id: uuid.UUID) -> Response:
        with service.cover(reader.id, book_id) as cover:
            return Response(
                cover.read(),
                media_type="image/png",
                headers={"X-Content-Type-Options": "nosniff"},
            )

    @router.get(
        "/books/{book_id}/content",
        response_class=Response,
        responses={
            200: {"content": {media: {} for media in _MEDIA_TYPES.values()}},
            404: {"model": ErrorOut},
        },
    )
    def book_content(reader: Reader, book_id: uuid.UUID) -> Response:
        book_format, content = service.content(reader.id, book_id)
        return StreamingResponse(
            _chunks(content),
            media_type=_MEDIA_TYPES[book_format],
            headers=_BOOK_HEADERS,
        )

    @router.post(
        "/books/{book_id}/open-failures",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={404: {"model": ErrorOut}},
    )
    def book_open_failed(reader: Reader, book_id: uuid.UUID) -> None:
        service.report_open_failure(reader.id, book_id)

    @router.delete(
        "/books/{book_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={404: {"model": ErrorOut}},
    )
    def delete_book(reader: Reader, book_id: uuid.UUID) -> None:
        service.delete(reader.id, book_id)

    @app.exception_handler(LibraryError)
    def refuse(_: Request, err: LibraryError) -> JSONResponse:
        code, reason = _ANSWERS[type(err)]
        return JSONResponse({"code": reason}, status_code=code)

    @app.exception_handler(UploadRejectedError)
    def reject(_: Request, err: UploadRejectedError) -> JSONResponse:
        too_large = err.reason == RejectReason.TOO_LARGE
        code = (
            status.HTTP_413_CONTENT_TOO_LARGE
            if too_large
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        return JSONResponse({"code": err.reason}, status_code=code)

    @app.exception_handler(DuplicateUploadError)
    def duplicate(_: Request, err: DuplicateUploadError) -> JSONResponse:
        body = DuplicateOut(
            code="duplicate_upload", book_id=err.book.id, title=err.book.title
        )
        return JSONResponse(
            body.model_dump(mode="json"), status_code=status.HTTP_409_CONFLICT
        )

    app.include_router(router)


def _chunks(content: BinaryIO) -> Iterator[bytes]:
    with content:
        while chunk := content.read(_CHUNK):
            yield chunk


def _out(book: Book) -> BookOut:
    cover_url = f"/api/books/{book.id}/cover" if book.has_cover else None
    return BookOut(
        id=book.id,
        title=book.title,
        author=book.author,
        status=book.status,
        cover_url=cover_url,
        failure=book.failure,
    )
