"""Library rows in Postgres."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Connection,
    DateTime,
    Engine,
    MetaData,
    Table,
    Text,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import UUID

from ebookdrop.conversion.port import BookFormat
from ebookdrop.library.domain import Book, BookEvent, BookStatus, FileName

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


class LibraryStore:
    """Reads and writes books, conversion jobs and book events."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add_upload(
        self, book_id: uuid.UUID, reader_id: uuid.UUID, name: FileName, at: datetime
    ) -> Book:
        """Insert the book, its outbox job and its events in one transaction (P1)."""
        row = {
            "id": book_id,
            "reader_id": reader_id,
            "file_name": name.value,
            "title": name.value,
            "status": BookStatus.PROCESSING,
            "has_cover": False,
            "received_at": at,
        }
        with self._engine.begin() as connection:
            connection.execute(insert(_books), row)
            connection.execute(insert(_jobs), {"book_id": book_id, "queued_at": at})
            _record(
                connection,
                book_id,
                [BookEvent.UPLOAD_RECEIVED, BookEvent.CONVERSION_QUEUED],
                at,
            )
        return Book(book_id, name.value, None, BookStatus.PROCESSING, False)

    def list_books(self, reader_id: uuid.UUID) -> list[Book]:
        """Return the reader's books, newest first."""
        query = (
            select(_books)
            .where(_books.c.reader_id == reader_id)
            .order_by(_books.c.received_at.desc(), _books.c.id)
        )
        with self._engine.connect() as connection:
            rows = connection.execute(query).all()
        return [
            Book(r.id, r.title, r.author, BookStatus(r.status), r.has_cover)
            for r in rows
        ]

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


def _record(
    connection: Connection,
    book_id: uuid.UUID,
    names: Sequence[BookEvent],
    at: datetime,
) -> None:
    connection.execute(
        insert(_events), [{"book_id": book_id, "name": n, "at": at} for n in names]
    )
