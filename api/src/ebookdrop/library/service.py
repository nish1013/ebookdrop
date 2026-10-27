"""Library commands: upload a book, the library list and the book read."""

import logging
import uuid
from typing import BinaryIO

from ebookdrop.clock import Clock
from ebookdrop.conversion.port import BookFormat
from ebookdrop.inspection.port import (
    FileRefusedError,
    InspectorPort,
    InspectorUnavailableError,
)
from ebookdrop.library.domain import (
    Book,
    BookNotFoundError,
    DuplicateUploadError,
    FileName,
    InspectUnavailableError,
    IntakeEvent,
    ReceivedFile,
    RejectReason,
    UploadRejectedError,
)
from ebookdrop.library.store import LibraryStore, NewUpload
from ebookdrop.storage import StoragePort

_log = logging.getLogger(__name__)


def original_key(book_id: uuid.UUID) -> str:
    """The storage key of the uploaded file."""
    return f"books/{book_id}/original"


def book_key(book_id: uuid.UUID, book_format: BookFormat) -> str:
    """The storage key of the readable book."""
    return f"books/{book_id}/book.{book_format}"


def cover_key(book_id: uuid.UUID) -> str:
    """The storage key of the PNG cover."""
    return f"books/{book_id}/cover.png"


def stored_keys(book_id: uuid.UUID, book_format: BookFormat | None) -> list[str]:
    """The storage keys of every file a book can have outside staging."""
    keys = [original_key(book_id), cover_key(book_id)]
    if book_format is not None:
        keys.append(book_key(book_id, book_format))
    return keys


def staging_key(book_id: uuid.UUID, book_key: str) -> str:
    """The staging key of a converted file before `BookReady` (decision 23)."""
    return f"staging/{book_id}/{book_key.rsplit('/', 1)[-1]}"


class LibraryService:
    """Runs the library commands on one store, storage, inspector and clock."""

    def __init__(
        self,
        store: LibraryStore,
        storage: StoragePort,
        clock: Clock,
        inspector: InspectorPort,
    ) -> None:
        self._store = store
        self._storage = storage
        self._clock = clock
        self._inspector = inspector

    def upload(self, reader_id: uuid.UUID, received: ReceivedFile) -> Book:
        """Inspect a fully received file, then add it as a book (R5, R6, R10).

        The file is saved before the transaction, so no row lock waits on disk
        writes. A refused or failed add deletes it.

        Raise `UploadRejectedError`, `DuplicateUploadError` or
        `InspectUnavailableError`. Each reject is recorded.
        """
        name = FileName.parse(received.raw_name)
        self._inspect(reader_id, received)
        book_id = uuid.uuid4()
        upload = NewUpload(
            book_id,
            reader_id,
            name,
            received.sha256,
            received.size,
            self._clock.now(),
        )
        key = original_key(book_id)
        try:
            with received.path.open("rb") as source:
                self._storage.save(key, source)
            return self._add(upload)
        except Exception:
            self._storage.delete(key)
            raise

    def reject(self, reader_id: uuid.UUID, reason: RejectReason) -> UploadRejectedError:
        """Record `UploadRejected(reason)` and return the error to raise."""
        self._store.record_intake(
            reader_id, IntakeEvent.UPLOAD_REJECTED, reason, self._clock.now()
        )
        return UploadRejectedError(reason)

    def abandon(self, reader_id: uuid.UUID) -> None:
        """Record `UploadAbandoned`: the transfer stopped before the last byte."""
        self._store.record_intake(
            reader_id, IntakeEvent.UPLOAD_ABANDONED, None, self._clock.now()
        )

    def books(self, reader_id: uuid.UUID) -> list[Book]:
        """Return the reader's books, newest first."""
        return self._store.list_books(reader_id)

    def cover(self, reader_id: uuid.UUID, book_id: uuid.UUID) -> BinaryIO:
        """Open the cover of the reader's book. Raise `BookNotFoundError`."""
        if not self._store.has_cover(reader_id, book_id):
            raise self._not_found(reader_id, book_id)
        return self._storage.open(cover_key(book_id))

    def content(
        self, reader_id: uuid.UUID, book_id: uuid.UUID
    ) -> tuple[BookFormat, BinaryIO]:
        """`OpenBook`: open the reader's own Ready book. Raise `BookNotFoundError`."""
        book_format = self._store.ready_format(reader_id, book_id)
        if book_format is None:
            raise self._not_found(reader_id, book_id)
        return book_format, self._storage.open(book_key(book_id, book_format))

    def report_open_failure(self, reader_id: uuid.UUID, book_id: uuid.UUID) -> None:
        """Record `BookOpenFailed` on the reader's Ready book (decision 15).

        Raise `BookNotFoundError`.
        """
        if not self._store.record_open_failure(reader_id, book_id, self._clock.now()):
            raise self._not_found(reader_id, book_id)

    def delete(self, reader_id: uuid.UUID, book_id: uuid.UUID) -> None:
        """`DeleteBook`: remove the reader's own book row, and queue P4 (R13).

        Raise `BookNotFoundError`.
        """
        if not self._store.delete_book(reader_id, book_id, self._clock.now()):
            raise self._not_found(reader_id, book_id)

    def _not_found(self, reader_id: uuid.UUID, book_id: uuid.UUID) -> BookNotFoundError:
        owner = self._store.owner(book_id)
        if owner is not None and owner != reader_id:
            _log.warning(
                "BookAccessDenied",
                extra={"reader_id": reader_id, "book_id": book_id},
            )
        return BookNotFoundError()

    def _add(self, upload: NewUpload) -> Book:
        try:
            return self._store.add_upload(upload)
        except UploadRejectedError as rejected:
            raise self.reject(upload.reader_id, rejected.reason) from None
        except DuplicateUploadError:
            self._store.record_intake(
                upload.reader_id,
                IntakeEvent.DUPLICATE_UPLOAD_DETECTED,
                None,
                self._clock.now(),
            )
            raise

    def _inspect(self, reader_id: uuid.UUID, received: ReceivedFile) -> None:
        try:
            self._inspector.inspect(received.path)
        except FileRefusedError as refused:
            raise self.reject(reader_id, RejectReason(refused.refusal)) from None
        except InspectorUnavailableError as err:
            raise InspectUnavailableError from err
