import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from ebookdrop.conversion.port import BookFormat, Conversion, ConverterPort
from ebookdrop.library.conversion_jobs import ConversionJobs
from ebookdrop.library.service import LibraryService
from ebookdrop.library.store import LibraryStore
from ebookdrop.storage import LocalDiskStorage
from tests.api.conftest import events, upload
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


@pytest.fixture
def converter() -> ConverterPort:
    return DuneConverter()


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
    }
    cover = client.get(listed["cover_url"])
    assert cover.status_code == 200
    assert cover.headers["content-type"] == "image/png"
    assert cover.content == COVER


def test_s6_ac2_p3_again_for_one_conversion_gives_no_second_book_ready(
    client: TestClient,
    engine: Engine,
    storage: LocalDiskStorage,
    clock: FakeClock,
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
    library = LibraryService(LibraryStore(engine), storage, clock)

    assert library.mark_ready(uuid.UUID(str(book["id"])), again) is False

    assert events(engine, book["id"]).count("book_ready") == 1
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM books")).scalar() == 1
