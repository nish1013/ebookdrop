"""Library values and rules."""

import uuid
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

MAX_FILE_NAME_LENGTH = 255
MAX_FILE_BYTES = 50 * 1024 * 1024
QUOTA_BYTES = 1024 * 1024 * 1024
MAX_DETAIL_LENGTH = 255
UNKNOWN_AUTHOR = "Unknown author"


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
    SANDBOX_ESCAPE_BLOCKED = "sandbox_escape_blocked"
    CONVERSION_FAILED = "conversion_failed"


class IntakeEvent(StrEnum):
    """The names of the recorded intake events that make no book."""

    UPLOAD_REJECTED = "upload_rejected"
    UPLOAD_ABANDONED = "upload_abandoned"
    DUPLICATE_UPLOAD_DETECTED = "duplicate_upload_detected"


class RejectReason(StrEnum):
    """Why an upload does not become a book (event 5)."""

    TOO_LARGE = "too_large"
    NOT_EPUB_OR_PDF = "not_epub_or_pdf"
    DRM_PROTECTED = "drm_protected"
    PASSWORD_PROTECTED = "password_protected"  # noqa: S105
    DAMAGED = "damaged"
    OVER_QUOTA = "over_quota"


class LibraryError(Exception):
    """Root of the library errors."""


class InvalidFileNameError(LibraryError):
    """The upload has no usable file name."""


class InvalidUploadError(LibraryError):
    """The request holds no complete file part."""


class UploadRejectedError(LibraryError):
    """The upload breaks an intake rule. The reason names it."""

    def __init__(self, reason: RejectReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


class DuplicateUploadError(LibraryError):
    """The reader already owns a book with the same bytes (R6)."""

    def __init__(self, book: "Book") -> None:
        super().__init__(str(book.id))
        self.book = book


class UploadAbandonedError(LibraryError):
    """The transfer stopped before the last byte (event 4)."""


class InspectUnavailableError(LibraryError):
    """The sandbox could not inspect the file. The reader can try again."""


class BookNotFoundError(LibraryError):
    """No book with this id belongs to the reader (decision 16)."""


@dataclass(frozen=True)
class FileName:
    """The last part of an uploaded file name, without outer spaces."""

    value: str

    @classmethod
    def parse(cls, raw: str | None) -> "FileName":
        """Keep the last path part and trim it. Raise `InvalidFileNameError`."""
        value = (raw or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
        if not value or len(value) > MAX_FILE_NAME_LENGTH:
            raise InvalidFileNameError
        return cls(value)


@dataclass(frozen=True)
class BookDetails:
    """The title and author the library shows. Neither is ever empty."""

    title: str
    author: str

    @classmethod
    def extracted(
        cls, title: str | None, author: str | None, file_name: FileName
    ) -> "BookDetails":
        """Clean the details read from a book. A missing one gets its fallback.

        The title falls back to the file name without its extension, the author
        to "Unknown author" (decision 11).
        """
        raise NotImplementedError


@dataclass(frozen=True)
class Book:
    """One book as the library list shows it."""

    id: uuid.UUID
    title: str
    author: str | None
    status: BookStatus
    has_cover: bool


@dataclass(frozen=True)
class ReceivedFile:
    """An upload whose last byte arrived, in a work file."""

    raw_name: str | None
    path: Path
    size: int
    sha256: str
