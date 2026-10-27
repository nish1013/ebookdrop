"""Library rows in Postgres."""

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Connection,
    DateTime,
    Engine,
    MetaData,
    Row,
    Table,
    Text,
    delete,
    exists,
    insert,
    literal,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from ebookdrop.conversion.port import BookFormat, Failure
from ebookdrop.library.domain import (
    QUOTA_BYTES,
    Book,
    BookDetails,
    BookEvent,
    BookStatus,
    DuplicateUploadError,
    FileName,
    IntakeEvent,
    RejectReason,
    UploadRejectedError,
)

ONE_BOOK_PER_FILE = "books_reader_sha256"

_metadata = MetaData()
_books = Table(
    "books",
    _metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("reader_id", UUID(as_uuid=True)),
    Column("file_name", Text),
    Column("title", Text),
    Column("author", Text),
    Column("format", Text),
    Column("status", Text),
    Column("has_cover", Boolean),
    Column("received_at", DateTime(timezone=True)),
    Column("ready_at", DateTime(timezone=True)),
    Column("sha256", Text),
    Column("size", BigInteger),
    Column("failure", Text),
)
_libraries = Table(
    "libraries",
    _metadata,
    Column("reader_id", UUID(as_uuid=True), primary_key=True),
    Column("bytes_used", BigInteger),
)
_intake_events = Table(
    "intake_events",
    _metadata,
    Column("reader_id", UUID(as_uuid=True)),
    Column("name", Text),
    Column("reason", Text),
    Column("at", DateTime(timezone=True)),
)
_jobs = Table(
    "conversion_jobs",
    _metadata,
    Column("book_id", UUID(as_uuid=True), primary_key=True),
    Column("queued_at", DateTime(timezone=True)),
    Column("started_at", DateTime(timezone=True)),
)
_events = Table(
    "book_events",
    _metadata,
    Column("book_id", UUID(as_uuid=True)),
    Column("name", Text),
    Column("at", DateTime(timezone=True)),
)
_removals = Table(
    "file_removals",
    _metadata,
    Column("book_id", UUID(as_uuid=True), primary_key=True),
    Column("format", Text),
    Column("queued_at", DateTime(timezone=True)),
)


@dataclass(frozen=True)
class NewUpload:
    """A received and inspected file, ready to become a book."""

    book_id: uuid.UUID
    reader_id: uuid.UUID
    name: FileName
    sha256: str
    size: int
    at: datetime


@dataclass(frozen=True)
class WaitingRemoval:
    """A deleted book whose files P4 must remove."""

    book_id: uuid.UUID
    format: BookFormat | None


class LibraryStore:
    """Reads and writes books, conversion jobs and book events."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add_upload(self, upload: NewUpload) -> Book:
        """Add the book under R6 and R10 in one transaction.

        The commit makes the book and its outbox job (P1) visible together.
        """
        row = {
            "id": upload.book_id,
            "reader_id": upload.reader_id,
            "file_name": upload.name.value,
            "title": upload.name.value,
            "status": BookStatus.PROCESSING,
            "has_cover": False,
            "received_at": upload.at,
            "sha256": upload.sha256,
            "size": upload.size,
        }
        try:
            with self._engine.begin() as connection:
                connection.execute(insert(_books), row)
                if not _use_quota(connection, upload.reader_id, upload.size):
                    raise UploadRejectedError(RejectReason.OVER_QUOTA)
                connection.execute(
                    insert(_jobs), {"book_id": upload.book_id, "queued_at": upload.at}
                )
                _record(
                    connection,
                    upload.book_id,
                    [BookEvent.UPLOAD_RECEIVED, BookEvent.CONVERSION_QUEUED],
                    upload.at,
                )
        except IntegrityError as err:
            if _constraint(err) != ONE_BOOK_PER_FILE:
                raise
            raise DuplicateUploadError(
                self._book_by_file(upload.reader_id, upload.sha256)
            ) from None
        return Book(
            upload.book_id, upload.name.value, None, BookStatus.PROCESSING, False
        )

    def record_intake(
        self,
        reader_id: uuid.UUID,
        name: IntakeEvent,
        reason: RejectReason | None,
        at: datetime,
    ) -> None:
        """Append one intake event that made no book."""
        row = {"reader_id": reader_id, "name": name, "reason": reason, "at": at}
        with self._engine.begin() as connection:
            connection.execute(insert(_intake_events), row)

    def list_books(self, reader_id: uuid.UUID) -> list[Book]:
        """Return the reader's books, newest first."""
        query = (
            select(_books)
            .where(_books.c.reader_id == reader_id)
            .order_by(_books.c.received_at.desc(), _books.c.id)
        )
        with self._engine.connect() as connection:
            rows = connection.execute(query).all()
        return [_book(r) for r in rows]

    def has_cover(self, reader_id: uuid.UUID, book_id: uuid.UUID) -> bool:
        """Say if the reader's own book has a cover. A foreign book has none."""
        query = select(_books.c.has_cover).where(
            _books.c.id == book_id, _books.c.reader_id == reader_id
        )
        with self._engine.connect() as connection:
            return bool(connection.execute(query).scalar())

    def ready_format(
        self, reader_id: uuid.UUID, book_id: uuid.UUID
    ) -> BookFormat | None:
        """Return the format of the reader's own Ready book, else `None`."""
        query = select(_books.c.format).where(
            _books.c.id == book_id,
            _books.c.reader_id == reader_id,
            _books.c.status == BookStatus.READY,
        )
        with self._engine.connect() as connection:
            found = connection.execute(query).scalar()
        return BookFormat(found) if found else None

    def record_open_failure(
        self, reader_id: uuid.UUID, book_id: uuid.UUID, at: datetime
    ) -> bool:
        """Record `BookOpenFailed` on the reader's own Ready book. `False` when not.

        The status stays Ready (decision 15).
        """
        ready = select(
            _books.c.id, literal(BookEvent.BOOK_OPEN_FAILED.value), literal(at)
        ).where(
            _books.c.id == book_id,
            _books.c.reader_id == reader_id,
            _books.c.status == BookStatus.READY,
        )
        recorded = (
            insert(_events)
            .from_select(["book_id", "name", "at"], ready)
            .returning(_events.c.book_id)
        )
        with self._engine.begin() as connection:
            return connection.execute(recorded).first() is not None

    def owner(self, book_id: uuid.UUID) -> uuid.UUID | None:
        """Return the reader who owns the book, for the access log only.

        This is the one read with no owner filter. No answer may depend on it.
        """
        query = select(_books.c.reader_id).where(_books.c.id == book_id)
        with self._engine.connect() as connection:
            found: uuid.UUID | None = connection.execute(query).scalar()
        return found

    def waiting_jobs(self, limit: int) -> list[uuid.UUID]:
        """Return the oldest jobs that no run has started."""
        query = (
            select(_jobs.c.book_id)
            .where(_jobs.c.started_at.is_(None))
            .order_by(_jobs.c.queued_at)
            .limit(limit)
        )
        with self._engine.connect() as connection:
            return list(connection.execute(query).scalars())

    def start_job(self, book_id: uuid.UUID, at: datetime) -> FileName | None:
        """Start the job once per upload id, and return the uploaded file name.

        Return `None` when the job already started or its book is gone.
        """
        claim = (
            update(_jobs)
            .where(
                _jobs.c.book_id == book_id,
                _jobs.c.started_at.is_(None),
                _books.c.id == _jobs.c.book_id,
            )
            .values(started_at=at)
            .returning(_books.c.file_name)
        )
        with self._engine.begin() as connection:
            name = connection.execute(claim).scalar()
            if name is None:
                return None
            _record(connection, book_id, [BookEvent.CONVERSION_STARTED], at)
        return FileName(name)

    def record(
        self, book_id: uuid.UUID, names: Sequence[BookEvent], at: datetime
    ) -> None:
        """Append the events of one book."""
        with self._engine.begin() as connection:
            _record(connection, book_id, names, at)

    def mark_ready(
        self,
        book_id: uuid.UUID,
        book_format: BookFormat,
        details: BookDetails,
        has_cover: bool,
        at: datetime,
        move: Callable[[], None],
    ) -> bool:
        """Move a Processing book to Ready with `BookReady`. `False` when not (R13).

        `move` runs inside the transaction, after the update, so the book and its
        files become Ready together.
        """
        ready = (
            update(_books)
            .where(_books.c.id == book_id, _books.c.status == BookStatus.PROCESSING)
            .values(
                status=BookStatus.READY,
                format=book_format,
                title=details.title,
                author=details.author,
                has_cover=has_cover,
                ready_at=at,
            )
        )
        with self._engine.begin() as connection:
            if connection.execute(ready).rowcount != 1:
                return False
            move()
            _record(connection, book_id, [BookEvent.BOOK_READY], at)
        return True

    def fail(
        self, book_id: uuid.UUID, failure: Failure, escape: bool, at: datetime
    ) -> bool:
        """Move a Processing book to Failed with `ConversionFailed`. R13 holds.

        An escape is recorded as `SandboxEscapeBlocked` first, whatever the status.
        """
        failed = (
            update(_books)
            .where(_books.c.id == book_id, _books.c.status == BookStatus.PROCESSING)
            .values(status=BookStatus.FAILED, failure=failure)
        )
        with self._engine.begin() as connection:
            if escape:
                _record(connection, book_id, [BookEvent.SANDBOX_ESCAPE_BLOCKED], at)
            if connection.execute(failed).rowcount != 1:
                return False
            _record(connection, book_id, [BookEvent.CONVERSION_FAILED], at)
        return True

    def fail_stuck(self, received_by: datetime, at: datetime) -> int:
        """Fail each book still Processing that was received by `received_by` (P2).

        The status condition is the R13 guard against a `MarkBookReady` that
        commits first. Return how many books failed.
        """
        stuck = (
            update(_books)
            .where(
                _books.c.status == BookStatus.PROCESSING,
                _books.c.received_at <= received_by,
            )
            .values(status=BookStatus.FAILED, failure=Failure.STUCK)
            .returning(_books.c.id)
        )
        with self._engine.begin() as connection:
            failed = list(connection.execute(stuck).scalars())
            for book_id in failed:
                _record(connection, book_id, [BookEvent.CONVERSION_FAILED], at)
        return len(failed)

    def delete_book(
        self, reader_id: uuid.UUID, book_id: uuid.UUID, at: datetime
    ) -> bool:
        """Remove the reader's own book row. `False` when the reader has none.

        One transaction lowers the bytes used, queues P4 and records
        `BookDeleted`, or `BookDeletedDuringConversion` for a Processing book.
        """
        removed = (
            delete(_books)
            .where(_books.c.id == book_id, _books.c.reader_id == reader_id)
            .returning(_books.c.status, _books.c.size, _books.c.format)
        )
        with self._engine.begin() as connection:
            row = connection.execute(removed).first()
            if row is None:
                return False
            connection.execute(
                update(_libraries)
                .where(_libraries.c.reader_id == reader_id)
                .values(bytes_used=_libraries.c.bytes_used - row.size)
            )
            connection.execute(
                insert(_removals),
                {"book_id": book_id, "format": row.format, "queued_at": at},
            )
            name = (
                BookEvent.BOOK_DELETED_DURING_CONVERSION
                if row.status == BookStatus.PROCESSING
                else BookEvent.BOOK_DELETED
            )
            _record(connection, book_id, [name], at)
        return True

    def waiting_removals(self, limit: int) -> list[WaitingRemoval]:
        """Return the oldest deleted books whose files wait for P4."""
        query = (
            select(_removals.c.book_id, _removals.c.format)
            .order_by(_removals.c.queued_at)
            .limit(limit)
        )
        with self._engine.connect() as connection:
            rows = connection.execute(query).all()
        return [
            WaitingRemoval(r.book_id, BookFormat(r.format) if r.format else None)
            for r in rows
        ]

    def finish_removal(self, book_id: uuid.UUID, at: datetime) -> bool:
        """Record `BookFilesRemoved` once and end the wait. `False` when done before."""
        done = delete(_removals).where(_removals.c.book_id == book_id)
        with self._engine.begin() as connection:
            if connection.execute(done).rowcount != 1:
                return False
            _record(connection, book_id, [BookEvent.BOOK_FILES_REMOVED], at)
        return True

    def failed_to_clean(self, failed_before: datetime) -> list[uuid.UUID]:
        """Return each Failed book that failed before `failed_before` and kept files."""
        failed = select(_events.c.book_id).where(
            _events.c.name == BookEvent.CONVERSION_FAILED,
            _events.c.at < failed_before,
        )
        cleaned = exists().where(
            _events.c.book_id == _books.c.id,
            _events.c.name == BookEvent.FAILED_UPLOAD_CLEANED_UP,
        )
        query = select(_books.c.id).where(
            _books.c.status == BookStatus.FAILED,
            _books.c.id.in_(failed),
            ~cleaned,
        )
        with self._engine.connect() as connection:
            return list(connection.execute(query).scalars())

    def _book_by_file(self, reader_id: uuid.UUID, sha256: str) -> Book:
        query = select(_books).where(
            _books.c.reader_id == reader_id, _books.c.sha256 == sha256
        )
        with self._engine.connect() as connection:
            return _book(connection.execute(query).one())


def _book(row: Row[Any]) -> Book:
    failure = Failure(row.failure) if row.failure else None
    return Book(
        row.id,
        row.title,
        row.author,
        BookStatus(row.status),
        row.has_cover,
        failure,
    )


def _use_quota(connection: Connection, reader_id: uuid.UUID, size: int) -> bool:
    connection.execute(
        pg_insert(_libraries)
        .values(reader_id=reader_id, bytes_used=0)
        .on_conflict_do_nothing()
    )
    claim = (
        update(_libraries)
        .where(
            _libraries.c.reader_id == reader_id,
            _libraries.c.bytes_used + size <= QUOTA_BYTES,
        )
        .values(bytes_used=_libraries.c.bytes_used + size)
    )
    return connection.execute(claim).rowcount == 1


def _constraint(err: IntegrityError) -> str | None:
    diag = getattr(err.orig, "diag", None)
    return getattr(diag, "constraint_name", None)


def _record(
    connection: Connection,
    book_id: uuid.UUID,
    names: Sequence[BookEvent],
    at: datetime,
) -> None:
    connection.execute(
        insert(_events), [{"book_id": book_id, "name": n, "at": at} for n in names]
    )
