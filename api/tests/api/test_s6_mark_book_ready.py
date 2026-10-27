import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from ebookdrop.app import conversion_jobs
from ebookdrop.conversion.port import BookFormat, Conversion, ConverterPort
from ebookdrop.library.conversion_jobs import ConversionJobs
from ebookdrop.storage import LocalDiskStorage
from tests.api.conftest import events, upload
from tests.api.test_upload_storage import stored_files
from tests.conftest import FakeClock
from tests.samples import epub

DUNE = epub()
COVER = b"\x89PNG\r\n\x1a\ncover"


class DuneConverter:
    def convert(self, source: Path, work_dir: Path) -> Conversion:
        book = work_dir / "book.epub"
        book.write_bytes(source.read_bytes())
        cover = work_dir / "cover.png"
        cover.write_bytes(COVER)
        return Conversion(BookFormat.EPUB, book, "Dune", "Frank Herbert", cover)


class FailedMeanwhileConverter(DuneConverter):
    """Fails the book while its conversion runs, as the stuck check can."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def convert(self, source: Path, work_dir: Path) -> Conversion:
        with self._engine.begin() as connection:
            connection.execute(
                text("UPDATE books SET status = 'failed', failure = 'crashed'")
            )
        return super().convert(source, work_dir)


@pytest.fixture
def converter() -> ConverterPort:
    return DuneConverter()


@pytest.fixture
def failing_book_ready(engine: Engine) -> Iterator[None]:
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE FUNCTION refuse_ready() RETURNS trigger LANGUAGE plpgsql AS"
                " $$ BEGIN RAISE EXCEPTION 'book ready refused'; END $$;"
                " CREATE TRIGGER refuse_ready BEFORE INSERT ON book_events"
                " FOR EACH ROW WHEN (NEW.name = 'book_ready')"
                " EXECUTE FUNCTION refuse_ready();"
            )
        )
    yield
    with engine.begin() as connection:
        connection.execute(
            text(
                "DROP TRIGGER refuse_ready ON book_events;"
                " DROP FUNCTION refuse_ready();"
            )
        )


def test_s6_ac1_ready_book_shows_title_author_and_cover(
    client: TestClient, jobs: ConversionJobs, signed_in_ana: str
) -> None:
    book = upload(client, "dune.epub", DUNE)

    jobs.poll()

    [listed] = client.get("/api/books").json()
    assert listed == {
        "id": book["id"],
        "title": "Dune",
        "author": "Frank Herbert",
        "status": "ready",
        "cover_url": f"/api/books/{book['id']}/cover",
        "failure": None,
    }
    cover = client.get(listed["cover_url"])
    assert cover.status_code == 200
    assert cover.headers["content-type"] == "image/png"
    assert cover.content == COVER


def test_s6_ac2_p3_again_for_one_conversion_gives_no_second_book_ready(
    client: TestClient,
    engine: Engine,
    jobs: ConversionJobs,
    signed_in_ana: str,
    tmp_path: Path,
) -> None:
    book = upload(client, "dune.epub", DUNE)
    jobs.poll()
    work_dir = tmp_path / "again"
    work_dir.mkdir()
    (work_dir / "original").write_bytes(DUNE)
    again = DuneConverter().convert(work_dir / "original", work_dir)

    assert jobs.mark_ready(uuid.UUID(str(book["id"])), again) is False

    assert events(engine, book["id"]).count("book_ready") == 1
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM books")).scalar() == 1
    assert stored_files(tmp_path) == [
        f"books/{book['id']}/book.epub",
        f"books/{book['id']}/cover.png",
        f"books/{book['id']}/original",
    ]


def test_s6_ac2_book_that_left_processing_leaves_no_converted_file(
    client: TestClient,
    engine: Engine,
    clock: FakeClock,
    storage: LocalDiskStorage,
    signed_in_ana: str,
    tmp_path: Path,
) -> None:
    converter = FailedMeanwhileConverter(engine)
    jobs = conversion_jobs(engine, clock, storage, converter)
    book = upload(client, "dune.epub", DUNE)

    jobs.poll()

    assert "book_ready" not in events(engine, book["id"])
    assert stored_files(tmp_path) == [f"books/{book['id']}/original"]


def test_book_ready_that_does_not_commit_leaves_no_file_at_the_book_key(
    client: TestClient,
    engine: Engine,
    jobs: ConversionJobs,
    signed_in_ana: str,
    tmp_path: Path,
    failing_book_ready: None,
) -> None:
    book = upload(client, "dune.epub", DUNE)

    with pytest.raises(DBAPIError):
        jobs.poll()

    [listed] = client.get("/api/books").json()
    assert listed["status"] == "processing"
    assert stored_files(tmp_path) == [f"books/{book['id']}/original"]
