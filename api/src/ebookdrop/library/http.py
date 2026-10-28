"""Library endpoints."""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request, UploadFile, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from ebookdrop.identity.domain import SignedInReader
from ebookdrop.identity.http import ErrorOut
from ebookdrop.library.domain import (
    Book,
    BookNotFoundError,
    BookStatus,
    InvalidFileNameError,
    LibraryError,
)
from ebookdrop.library.service import LibraryService

_ANSWERS: dict[type[LibraryError], tuple[int, str]] = {
    InvalidFileNameError: (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "invalid_file_name",
    ),
    BookNotFoundError: (status.HTTP_404_NOT_FOUND, "book_not_found"),
}


class BookOut(BaseModel):
    """A book as the library list shows it."""

    id: uuid.UUID
    title: str
    author: str | None
    status: BookStatus
    cover_url: str | None


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

    @router.post("/books", status_code=status.HTTP_201_CREATED)
    def upload_book(reader: Reader, file: UploadFile) -> BookOut:
        return _out(service.upload(reader.id, file.filename, file.file))

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

    @app.exception_handler(LibraryError)
    def refuse(_: Request, err: LibraryError) -> JSONResponse:
        code, reason = _ANSWERS[type(err)]
        return JSONResponse({"code": reason}, status_code=code)

    app.include_router(router)


def _out(book: Book) -> BookOut:
    cover_url = f"/api/books/{book.id}/cover" if book.has_cover else None
    return BookOut(
        id=book.id,
        title=book.title,
        author=book.author,
        status=book.status,
        cover_url=cover_url,
    )
