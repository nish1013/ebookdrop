import uuid

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from ebookdrop.library.conversion_jobs import ConversionJobs
from ebookdrop.storage import LocalDiskStorage
from tests.api.conftest import events, upload
from tests.samples import epub, pdf

DUNE = epub()
ATLAS = pdf()


def test_s5_ac1_epub_upload_is_queued_started_and_normalised(
    client: TestClient, engine: Engine, jobs: ConversionJobs, signed_in_ana: str
) -> None:
    book = upload(client, "dune.epub", DUNE)

    assert jobs.poll() == 1

    assert events(engine, book["id"]) == [
        "upload_received",
        "conversion_queued",
        "conversion_started",
        "epub_normalised",
        "book_details_extracted",
        "book_ready",
    ]


def test_s5_ac2_pdf_upload_is_kept_as_is(
    client: TestClient,
    engine: Engine,
    storage: LocalDiskStorage,
    jobs: ConversionJobs,
    signed_in_ana: str,
) -> None:
    book = upload(client, "atlas.pdf", ATLAS)

    jobs.poll()

    names = events(engine, book["id"])
    assert names[3:5] == ["pdf_kept_as_is", "book_details_extracted"]
    assert "epub_normalised" not in names
    with storage.open(f"books/{book['id']}/book.pdf") as kept:
        assert kept.read() == ATLAS


def test_s5_ac7_second_run_of_p1_for_one_upload_converts_once(
    client: TestClient, engine: Engine, jobs: ConversionJobs, signed_in_ana: str
) -> None:
    book = upload(client, "dune.epub", DUNE)
    jobs.poll()

    jobs.run(uuid.UUID(str(book["id"])))

    assert events(engine, book["id"]).count("epub_normalised") == 1
    assert jobs.poll() == 0
