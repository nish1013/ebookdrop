import hashlib
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, text

from ebookdrop.conversion.port import BookFormat
from ebookdrop.library.domain import BookDetails, FileName
from ebookdrop.library.store import LibraryStore, NewUpload, WaitingRemoval

TEN = datetime(2026, 10, 27, 10, 0, tzinfo=UTC)


def _processing_book(
    store: LibraryStore, reader_id: uuid.UUID | None = None
) -> uuid.UUID:
    book_id = uuid.uuid4()
    store.add_upload(
        NewUpload(
            book_id,
            reader_id or uuid.uuid4(),
            FileName("dune.epub"),
            hashlib.sha256(book_id.bytes).hexdigest(),
            100,
            TEN,
        )
    )
    return book_id


def _wait_for_a_lock_wait(engine: Engine) -> None:
    query = text(
        "SELECT count(*) FROM pg_stat_activity"
        " WHERE wait_event_type = 'Lock' AND datname = current_database()"
    )
    for _ in range(500):
        with engine.connect() as connection:
            if connection.execute(query).scalar():
                return
        time.sleep(0.01)
    raise AssertionError("the second writer never waited on the book row")


def _status(engine: Engine, book_id: uuid.UUID) -> str:
    query = text("SELECT status FROM books WHERE id = :id")
    with engine.connect() as connection:
        status: str = connection.execute(query, {"id": book_id}).scalar_one()
    return status


def test_r13_p2_that_waits_on_p3_leaves_the_ready_book_ready(engine: Engine) -> None:
    store = LibraryStore(engine)
    book_id = _processing_book(store)
    stuck: list[int] = []
    p2 = threading.Thread(
        target=lambda: stuck.append(store.fail_stuck(TEN, TEN + timedelta(minutes=5)))
    )

    def move_while_p2_waits() -> None:
        p2.start()
        _wait_for_a_lock_wait(engine)

    ready = store.mark_ready(
        book_id,
        BookFormat.EPUB,
        BookDetails("Dune", "Frank Herbert"),
        False,
        TEN + timedelta(seconds=40),
        move_while_p2_waits,
    )
    p2.join(timeout=10)

    assert (ready, stuck) == (True, [0])
    assert _status(engine, book_id) == "ready"


def test_r13_delete_that_waits_on_p3_queues_the_ready_book_files(
    engine: Engine,
) -> None:
    store = LibraryStore(engine)
    reader_id = uuid.uuid4()
    book_id = _processing_book(store, reader_id)
    deleted: list[bool] = []
    delete = threading.Thread(
        target=lambda: deleted.append(
            store.delete_book(reader_id, book_id, TEN + timedelta(minutes=1))
        )
    )

    def move_while_delete_waits() -> None:
        delete.start()
        _wait_for_a_lock_wait(engine)

    ready = store.mark_ready(
        book_id,
        BookFormat.EPUB,
        BookDetails("Dune", "Frank Herbert"),
        True,
        TEN + timedelta(seconds=40),
        move_while_delete_waits,
    )
    delete.join(timeout=10)

    assert (ready, deleted) == (True, [True])
    assert store.waiting_removals(10) == [WaitingRemoval(book_id, BookFormat.EPUB)]
