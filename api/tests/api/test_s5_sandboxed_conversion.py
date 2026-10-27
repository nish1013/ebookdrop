from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from ebookdrop.app import conversion_jobs
from ebookdrop.conversion.docker import DockerConverter
from ebookdrop.conversion.port import BookFormat, ConverterPort
from ebookdrop.inspection.sandbox_check import PDF_MAGIC
from ebookdrop.library.conversion_jobs import ConversionJobs
from ebookdrop.storage import LocalDiskStorage
from tests.api.conftest import events, upload
from tests.conftest import FakeClock
from tests.samples import cut, epub, pdf

RECEIVED = ["upload_received", "conversion_queued", "conversion_started"]


class AcceptingInspector:
    """Lets a file through to the converter, as a file that the inspect missed."""

    def inspect(self, source: Path) -> BookFormat:
        head = source.read_bytes()[:1024]
        return BookFormat.PDF if PDF_MAGIC in head else BookFormat.EPUB


@pytest.fixture
def inspector() -> AcceptingInspector:
    return AcceptingInspector()


@pytest.fixture
def converter(image: str) -> ConverterPort:
    return DockerConverter(image)


def listed(client: TestClient, book: dict[str, object]) -> dict[str, object]:
    [found] = [b for b in client.get("/api/books").json() if b["id"] == book["id"]]
    item: dict[str, object] = found
    return item


def test_s5_ac3_cut_zip_fails_as_malformed(
    client: TestClient, engine: Engine, jobs: ConversionJobs, signed_in_ana: str
) -> None:
    book = upload(client, "broken.epub", cut(epub(padding=64 * 1024), 0.6))

    jobs.poll()

    assert events(engine, book["id"]) == [*RECEIVED, "conversion_failed"]
    assert listed(client, book)["status"] == "failed"
    assert listed(client, book)["failure"] == "malformed"


def test_s5_ac4_conversion_past_the_timeout_fails_as_timed_out(
    client: TestClient,
    engine: Engine,
    clock: FakeClock,
    storage: LocalDiskStorage,
    image: str,
    signed_in_ana: str,
) -> None:
    jobs = conversion_jobs(engine, clock, storage, DockerConverter(image, 0.5))
    book = upload(client, "slow.epub", epub(padding=4 * 1024 * 1024))

    jobs.poll()

    assert events(engine, book["id"]) == [*RECEIVED, "conversion_failed"]
    assert listed(client, book)["failure"] == "timed_out"


def test_s5_ac5_book_that_opens_a_socket_is_blocked_then_fails_as_crashed(
    client: TestClient,
    engine: Engine,
    clock: FakeClock,
    storage: LocalDiskStorage,
    evil_image: str,
    signed_in_ana: str,
) -> None:
    jobs = conversion_jobs(engine, clock, storage, DockerConverter(evil_image))
    book = upload(client, "evil.epub", epub())

    jobs.poll()

    assert events(engine, book["id"]) == [
        *RECEIVED,
        "sandbox_escape_blocked",
        "conversion_failed",
    ]
    assert listed(client, book)["failure"] == "crashed"


def test_s5_ac6_book_without_details_gets_the_fallbacks(
    client: TestClient,
    engine: Engine,
    storage: LocalDiskStorage,
    jobs: ConversionJobs,
    signed_in_ana: str,
) -> None:
    scan = pdf()
    book = upload(client, "scan.pdf", scan)

    jobs.poll()

    assert events(engine, book["id"])[3:] == [
        "pdf_kept_as_is",
        "book_details_extracted",
        "book_ready",
    ]
    assert listed(client, book) == {
        "id": book["id"],
        "title": "scan",
        "author": "Unknown author",
        "status": "ready",
        "cover_url": None,
        "failure": None,
    }
    with storage.open(f"books/{book['id']}/book.pdf") as kept:
        assert kept.read() == scan
    with pytest.raises(FileNotFoundError):
        storage.open(f"staging/{book['id']}/book.pdf")


def test_s5_ac8_epub_whose_page_1_does_not_render_fails_as_unreadable(
    client: TestClient, engine: Engine, jobs: ConversionJobs, signed_in_ana: str
) -> None:
    book = upload(client, "blank.epub", epub(blank=True))

    jobs.poll()

    assert events(engine, book["id"]) == [*RECEIVED, "conversion_failed"]
    assert listed(client, book)["status"] == "failed"
    assert listed(client, book)["failure"] == "unreadable"
