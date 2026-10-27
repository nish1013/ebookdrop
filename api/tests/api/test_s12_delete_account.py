import hashlib
import io
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, MetaData, text
from sqlalchemy.exc import DBAPIError

from ebookdrop.app import conversion_jobs, library_removal
from ebookdrop.conversion.port import (
    Conversion,
    ConversionFailedError,
    ConverterPort,
    Failure,
)
from ebookdrop.library.conversion_jobs import ConversionJobs
from ebookdrop.library.domain import FileName, ReaderGoneError
from ebookdrop.library.file_removal import FileRemoval
from ebookdrop.library.library_removal import LibraryRemoval
from ebookdrop.library.store import LibraryStore, NewUpload
from ebookdrop.storage import LocalDiskStorage
from tests.api.conftest import (
    reader_id,
    sign_in,
    sign_up,
    upload,
)
from tests.api.test_s6_mark_book_ready import DuneConverter
from tests.api.test_upload_storage import stored_files
from tests.conftest import FakeClock
from tests.samples import epub, pdf

DUNE = epub(title="Dune")
EMMA = epub(title="Emma", seed=1)
BAD = pdf(title="Bad")
ANA = "ana@example.com"

_KEYED_ROWS = {
    "accounts": "SELECT count(*) FROM accounts WHERE id = :reader",
    "sessions": "SELECT count(*) FROM sessions WHERE account_id = :reader",
    "sign_in_failures": "SELECT count(*) FROM sign_in_failures"
    " WHERE email_key = :email",
    "libraries": "SELECT count(*) FROM libraries WHERE reader_id = :reader",
    "books": "SELECT count(*) FROM books WHERE reader_id = :reader",
    "conversion_jobs": "SELECT count(*) FROM conversion_jobs"
    " WHERE book_id = ANY(:books)",
    "file_removals": "SELECT count(*) FROM file_removals WHERE book_id = ANY(:books)",
    "account_deletions": "SELECT count(*) FROM account_deletions"
    " WHERE reader_id = :reader",
}
_EVENT_TABLES = {"book_events", "intake_events", "alembic_version"}


class FailPdfConverter(DuneConverter):
    def convert(self, source: Path, work_dir: Path) -> Conversion:
        if source.read_bytes().startswith(b"%PDF"):
            raise ConversionFailedError(Failure.MALFORMED)
        return super().convert(source, work_dir)


class AccountDeletedMeanwhileConverter(DuneConverter):
    """Ana deletes her account, and P6 runs, while her book converts."""

    def __init__(self, client: TestClient, libraries: LibraryRemoval) -> None:
        self._client = client
        self._libraries = libraries

    def convert(self, source: Path, work_dir: Path) -> Conversion:
        assert self._client.delete("/api/accounts/me").status_code == 204
        assert self._libraries.poll() == 1
        return super().convert(source, work_dir)


@pytest.fixture
def converter() -> ConverterPort:
    return FailPdfConverter()


@pytest.fixture
def libraries(engine: Engine, clock: FakeClock) -> LibraryRemoval:
    return library_removal(engine, clock)


@contextmanager
def _refused_removal_inserts(engine: Engine) -> Iterator[None]:
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE FUNCTION refuse_removal() RETURNS trigger LANGUAGE plpgsql AS"
                " $$ BEGIN RAISE EXCEPTION 'removal insert refused'; END $$;"
                " CREATE TRIGGER refuse_removal BEFORE INSERT ON file_removals"
                " FOR EACH ROW EXECUTE FUNCTION refuse_removal();"
            )
        )
    try:
        yield
    finally:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "DROP TRIGGER refuse_removal ON file_removals;"
                    " DROP FUNCTION refuse_removal();"
                )
            )


def _remains(
    engine: Engine, tmp_path: Path, reader: uuid.UUID, books: list[str]
) -> list[str]:
    """List each table with rows of the reader, and each file under her keys."""
    tables = MetaData()
    tables.reflect(engine)
    assert set(tables.tables) == set(_KEYED_ROWS) | _EVENT_TABLES
    params = {
        "reader": reader,
        "email": ANA,
        "books": [uuid.UUID(b) for b in books],
    }
    found = []
    with engine.connect() as connection:
        for table, query in _KEYED_ROWS.items():
            rows = connection.execute(text(query), params).scalar_one()
            if rows:
                found.append(f"{table}: {rows}")
    prefixes = tuple(f"{area}/{b}/" for b in books for area in ("books", "staging"))
    return found + [f for f in stored_files(tmp_path) if f.startswith(prefixes)]


def _three_books(
    client: TestClient, jobs: ConversionJobs, storage: LocalDiskStorage
) -> list[str]:
    """Give Ana a Ready, a Failed and a Processing book with staged files."""
    ready = upload(client, "dune.epub", DUNE)
    failed = upload(client, "bad.pdf", BAD)
    jobs.poll()
    processing = upload(client, "emma.epub", EMMA)
    for name in ("book.epub", "cover.png"):
        storage.save(f"staging/{processing['id']}/{name}", io.BytesIO(b"staged"))
    statuses = [b["status"] for b in client.get("/api/books").json()]
    assert sorted(statuses) == ["failed", "processing", "ready"]
    return [str(ready["id"]), str(failed["id"]), str(processing["id"])]


def test_s12_ac1_ana_deletes_her_account_and_no_row_or_file_of_her_3_books_stays(
    client: TestClient,
    engine: Engine,
    jobs: ConversionJobs,
    libraries: LibraryRemoval,
    removals: FileRemoval,
    storage: LocalDiskStorage,
    signed_in_ana: str,
    tmp_path: Path,
) -> None:
    reader = reader_id(engine, ANA)
    books = _three_books(client, jobs, storage)
    assert sign_in(client, ANA, "wrong horse battery") == 401
    token = client.cookies["session"]

    assert client.delete("/api/accounts/me").status_code == 204

    assert sign_in(client, ANA) == 401
    client.cookies.set("session", token)
    assert client.get("/api/books").status_code == 401
    assert libraries.poll() == 1
    assert removals.poll() == 3
    assert jobs.poll() == 0
    assert _remains(engine, tmp_path, reader, books) == []


def test_s12_ac2_ana_signs_up_again_with_the_same_email_and_has_an_empty_library(
    client: TestClient,
    engine: Engine,
    jobs: ConversionJobs,
    libraries: LibraryRemoval,
    removals: FileRemoval,
    signed_in_ana: str,
) -> None:
    upload(client, "dune.epub", DUNE)
    jobs.poll()
    assert client.delete("/api/accounts/me").status_code == 204

    assert sign_up(client, ANA) == 201
    assert sign_in(client, ANA) == 204
    assert client.get("/api/books").json() == []
    upload(client, "dune.epub", DUNE)
    libraries.poll()
    removals.poll()

    assert client.get("/api/sessions/current").status_code == 200
    [book] = client.get("/api/books").json()
    assert book["status"] == "processing"


def test_every_session_of_ana_ends_with_her_account(
    client: TestClient, ana: str
) -> None:
    tokens = []
    for _ in range(2):
        assert sign_in(client, ana) == 204
        tokens.append(client.cookies["session"])

    assert client.delete("/api/accounts/me").status_code == 204

    for token in tokens:
        client.cookies.set("session", token)
        assert client.get("/api/sessions/current").status_code == 401


def test_delete_account_with_no_session_is_refused_and_the_account_stays(
    client: TestClient, ana: str
) -> None:
    assert client.delete("/api/accounts/me").status_code == 401
    assert sign_in(client, ana) == 204


def test_p6_that_stops_part_way_runs_again_to_the_same_end_state(
    client: TestClient,
    engine: Engine,
    jobs: ConversionJobs,
    libraries: LibraryRemoval,
    removals: FileRemoval,
    storage: LocalDiskStorage,
    signed_in_ana: str,
    tmp_path: Path,
) -> None:
    reader = reader_id(engine, ANA)
    books = _three_books(client, jobs, storage)
    assert client.delete("/api/accounts/me").status_code == 204

    with _refused_removal_inserts(engine), pytest.raises(DBAPIError):
        libraries.poll()

    assert "books: 3" in _remains(engine, tmp_path, reader, books)
    assert libraries.poll() == 1
    assert libraries.poll() == 0
    assert removals.poll() == 3
    assert _remains(engine, tmp_path, reader, books) == []


def test_r13_a_conversion_that_ends_after_the_account_delete_brings_no_book_back(
    client: TestClient,
    engine: Engine,
    clock: FakeClock,
    libraries: LibraryRemoval,
    removals: FileRemoval,
    storage: LocalDiskStorage,
    signed_in_ana: str,
    tmp_path: Path,
) -> None:
    reader = reader_id(engine, ANA)
    book = upload(client, "dune.epub", DUNE)
    converter = AccountDeletedMeanwhileConverter(client, libraries)

    conversion_jobs(engine, clock, storage, converter).poll()
    removals.poll()

    assert _remains(engine, tmp_path, reader, [str(book["id"])]) == []


def test_an_upload_that_ends_after_the_account_delete_adds_no_book(
    client: TestClient,
    engine: Engine,
    clock: FakeClock,
    signed_in_ana: str,
    tmp_path: Path,
) -> None:
    reader = reader_id(engine, ANA)
    assert client.delete("/api/accounts/me").status_code == 204
    late = NewUpload(
        uuid.uuid4(),
        reader,
        FileName("dune.epub"),
        hashlib.sha256(DUNE).hexdigest(),
        len(DUNE),
        clock.now(),
    )

    with pytest.raises(ReaderGoneError):
        LibraryStore(engine).add_upload(late)

    assert _remains(engine, tmp_path, reader, [str(late.book_id)]) == []
