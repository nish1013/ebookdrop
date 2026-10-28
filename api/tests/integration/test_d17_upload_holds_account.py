import hashlib
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Connection, Engine, text

from ebookdrop.app import library_removal
from ebookdrop.identity.domain import Email
from ebookdrop.identity.store import IdentityStore
from ebookdrop.library.domain import FileName
from ebookdrop.library.store import LibraryStore, NewUpload
from tests.conftest import FakeClock

UPLOAD_GATE = 4217


@contextmanager
def _upload_gate(engine: Engine) -> Iterator[Connection]:
    """Hold each book insert after its account lock until the yielded commit."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE FUNCTION wait_at_gate() RETURNS trigger LANGUAGE plpgsql AS"
                f" $$ BEGIN PERFORM pg_advisory_xact_lock({UPLOAD_GATE});"
                " RETURN NEW; END $$;"
                " CREATE TRIGGER wait_at_gate BEFORE INSERT ON books"
                " FOR EACH ROW EXECUTE FUNCTION wait_at_gate();"
            )
        )
    holder = engine.connect()
    holder.begin()
    holder.execute(text(f"SELECT pg_advisory_xact_lock({UPLOAD_GATE})"))
    try:
        yield holder
    finally:
        holder.close()
        with engine.begin() as connection:
            connection.execute(
                text(
                    "DROP TRIGGER wait_at_gate ON books; DROP FUNCTION wait_at_gate();"
                )
            )


def _wait_for(engine: Engine, wait_event: str, query: str, what: str) -> None:
    waiting = text(
        "SELECT count(*) FROM pg_stat_activity"
        " WHERE datname = current_database() AND wait_event_type = 'Lock'"
        " AND wait_event = :event AND query ILIKE :query"
    )
    params = {"event": wait_event, "query": query}
    for _ in range(300):
        with engine.connect() as connection:
            if connection.execute(waiting, params).scalar():
                return
        time.sleep(0.01)
    raise AssertionError(f"{what} never waited")


def test_d17_an_account_delete_waits_for_an_open_upload_and_p6_removes_its_book(
    engine: Engine, clock: FakeClock
) -> None:
    identity = IdentityStore(engine)
    reader = identity.add_account(Email.parse("ana@example.com"), "h")
    upload = NewUpload(
        uuid.uuid4(),
        reader,
        FileName("dune.epub"),
        hashlib.sha256(b"dune").hexdigest(),
        100,
        clock.now(),
    )
    uploader = threading.Thread(target=LibraryStore(engine).add_upload, args=[upload])
    deleter = threading.Thread(
        target=identity.delete_account, args=[reader, clock.now()]
    )

    with _upload_gate(engine) as gate:
        uploader.start()
        _wait_for(engine, "advisory", "INSERT INTO books%", "the upload")
        deleter.start()
        try:
            _wait_for(
                engine, "transactionid", "DELETE FROM accounts%", "the account delete"
            )
            assert deleter.is_alive()
        finally:
            gate.commit()
            uploader.join(timeout=10)
            deleter.join(timeout=10)

    assert library_removal(engine, clock).poll() == 1
    with engine.connect() as connection:
        books = connection.execute(
            text("SELECT count(*) FROM books WHERE reader_id = :r"), {"r": reader}
        ).scalar_one()
        queued = (
            connection.execute(text("SELECT book_id FROM file_removals"))
            .scalars()
            .all()
        )
    assert (books, queued) == (0, [upload.book_id])
