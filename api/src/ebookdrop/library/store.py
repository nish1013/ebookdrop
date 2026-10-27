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
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from ebookdrop.conversion.port import BookFormat
from ebookdrop.library.domain import (
    QUOTA_BYTES,
    Book,
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


@dataclass(frozen=True)
class NewUpload:
    """A received and inspected file, ready to become a book."""

    book_id: uuid.UUID
    reader_id: uuid.UUID
    name: FileName
    sha256: str
    size: int
    at: datetime


class LibraryStore:
    """Reads and writes books, conversion jobs and book events."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add_upload(self, upload: NewUpload, save: Callable[[], None]) -> Book:
        """Add the book under R6 and R10, then `save` its file, in one transaction.

        The file is saved only when both guards pass. The commit then makes the
        book and its outbox job (P1) visible together.
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
                save()
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

    def start_job(self, book_id: uuid.UUID, at: datetime) -> bool:
        """Start the job once per upload id. Return `False` when it already started."""
        claim = (
            update(_jobs)
            .where(_jobs.c.book_id == book_id, _jobs.c.started_at.is_(None))
            .values(started_at=at)
        )
        with self._engine.begin() as connection:
            if connection.execute(claim).rowcount != 1:
                return False
            _record(connection, book_id, [BookEvent.CONVERSION_STARTED], at)
        return True

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
        title: str | None,
        author: str | None,
        has_cover: bool,
        at: datetime,
    ) -> bool:
        """Move a Processing book to Ready with `BookReady`. `False` when not (R13)."""
        values: dict[str, object] = {
            "status": BookStatus.READY,
            "format": book_format,
            "author": author,
            "has_cover": has_cover,
            "ready_at": at,
        }
        if title is not None:
            values["title"] = title
        ready = (
            update(_books)
            .where(_books.c.id == book_id, _books.c.status == BookStatus.PROCESSING)
            .values(values)
        )
        with self._engine.begin() as connection:
            if connection.execute(ready).rowcount != 1:
                return False
            _record(connection, book_id, [BookEvent.BOOK_READY], at)
        return True

    def _book_by_file(self, reader_id: uuid.UUID, sha256: str) -> Book:
        query = select(_books).where(
            _books.c.reader_id == reader_id, _books.c.sha256 == sha256
        )
        with self._engine.connect() as connection:
            return _book(connection.execute(query).one())


def _book(row: Row[Any]) -> Book:
    return Book(row.id, row.title, row.author, BookStatus(row.status), row.has_cover)


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
