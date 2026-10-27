"""Library values and rules."""

import uuid
from dataclasses import dataclass
from enum import StrEnum

MAX_FILE_NAME_LENGTH = 255


class BookStatus(StrEnum):
    """Where a book is on its way to the library."""

    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class BookEvent(StrEnum):
    """The names of the recorded book events. The metric counts them (decision 12)."""

    UPLOAD_RECEIVED = "upload_received"
    CONVERSION_QUEUED = "conversion_queued"
    CONVERSION_STARTED = "conversion_started"
    EPUB_NORMALISED = "epub_normalised"
    PDF_KEPT_AS_IS = "pdf_kept_as_is"
    BOOK_DETAILS_EXTRACTED = "book_details_extracted"
    BOOK_READY = "book_ready"


class LibraryError(Exception):
    """Root of the library errors."""


class InvalidFileNameError(LibraryError):
    """The upload has no usable file name."""


class BookNotFoundError(LibraryError):
    """No book with this id belongs to the reader (decision 16)."""


@dataclass(frozen=True)
class FileName:
    """The last part of an uploaded file name, without outer spaces."""

    value: str

    @classmethod
    def parse(cls, raw: str | None) -> "FileName":
        """Keep the last path part and trim it. Raise `InvalidFileNameError`."""
        raise NotImplementedError


@dataclass(frozen=True)
class Book:
    """One book as the library list shows it."""

    id: uuid.UUID
    title: str
    author: str | None
    status: BookStatus
    has_cover: bool
