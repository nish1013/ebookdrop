"""Library commands: upload a book, mark it ready, and the library list."""

import uuid
from typing import BinaryIO

from ebookdrop.clock import Clock
from ebookdrop.conversion.port import Conversion
from ebookdrop.library.domain import Book
from ebookdrop.library.store import LibraryStore
from ebookdrop.storage import StoragePort


class LibraryService:
    """Runs the library commands on one store, one storage and one clock."""

    def __init__(self, store: LibraryStore, storage: StoragePort, clock: Clock) -> None:
        self._store = store
        self._storage = storage
        self._clock = clock

    def upload(
        self, reader_id: uuid.UUID, raw_name: str | None, source: BinaryIO
    ) -> Book:
        """Store the file and record `UploadReceived` with its conversion job."""
        raise NotImplementedError

    def books(self, reader_id: uuid.UUID) -> list[Book]:
        """Return the reader's books, newest first."""
        raise NotImplementedError

    def cover(self, reader_id: uuid.UUID, book_id: uuid.UUID) -> BinaryIO:
        """Open the cover of the reader's book. Raise `BookNotFoundError`."""
        raise NotImplementedError

    def mark_ready(self, book_id: uuid.UUID, conversion: Conversion) -> bool:
        """P3: store the converted files and record `BookReady` once (R13)."""
        raise NotImplementedError
