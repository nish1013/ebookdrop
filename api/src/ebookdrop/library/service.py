"""Library commands: upload a book, mark it ready, and the library list."""

import uuid
from typing import BinaryIO

from ebookdrop.clock import Clock
from ebookdrop.conversion.port import Conversion
from ebookdrop.library.domain import Book, BookNotFoundError, FileName
from ebookdrop.library.store import LibraryStore
from ebookdrop.storage import StoragePort


def original_key(book_id: uuid.UUID) -> str:
    """The storage key of the uploaded file."""
    return f"books/{book_id}/original"


def cover_key(book_id: uuid.UUID) -> str:
    """The storage key of the PNG cover."""
    return f"books/{book_id}/cover.png"


class LibraryService:
    """Runs the library commands on one store, one storage and one clock."""

    def __init__(self, store: LibraryStore, storage: StoragePort, clock: Clock) -> None:
        self._store = store
        self._storage = storage
        self._clock = clock

    def upload(
        self, reader_id: uuid.UUID, raw_name: str | None, source: BinaryIO
    ) -> Book:
        """Store the file, then record `UploadReceived` with its conversion job (R5)."""
        name = FileName.parse(raw_name)
        book_id = uuid.uuid4()
        self._storage.save(original_key(book_id), source)
        return self._store.add_upload(book_id, reader_id, name, self._clock.now())

    def books(self, reader_id: uuid.UUID) -> list[Book]:
        """Return the reader's books, newest first."""
        return self._store.list_books(reader_id)

    def cover(self, reader_id: uuid.UUID, book_id: uuid.UUID) -> BinaryIO:
        """Open the cover of the reader's book. Raise `BookNotFoundError`."""
        if not self._store.has_cover(reader_id, book_id):
            raise BookNotFoundError
        return self._storage.open(cover_key(book_id))

    def mark_ready(self, book_id: uuid.UUID, conversion: Conversion) -> bool:
        """P3: store the converted files and record `BookReady` once (R13)."""
        with conversion.book.open("rb") as book:
            self._storage.save(f"books/{book_id}/book.{conversion.format}", book)
        if conversion.cover is not None:
            with conversion.cover.open("rb") as cover:
                self._storage.save(cover_key(book_id), cover)
        return self._store.mark_ready(
            book_id,
            conversion.format,
            conversion.title,
            conversion.author,
            conversion.cover is not None,
            self._clock.now(),
        )
