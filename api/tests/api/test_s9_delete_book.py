import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from ebookdrop.conversion.port import ConverterPort
from ebookdrop.library.conversion_jobs import ConversionJobs
from ebookdrop.library.file_removal import FileRemoval
from tests.api.conftest import (
    count,
    events,
    library_bytes,
    sign_in,
    sign_up,
    upload,
)
from tests.api.test_s6_mark_book_ready import DuneConverter
from tests.api.test_upload_storage import stored_files
from tests.samples import epub, pdf

DUNE = epub(title="Dune")
EMMA = pdf(title="Emma")


@pytest.fixture
def converter() -> ConverterPort:
    return DuneConverter()


@pytest.fixture
def failing_removal_insert(engine: Engine) -> Iterator[None]:
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE FUNCTION refuse_removal() RETURNS trigger LANGUAGE plpgsql AS"
                " $$ BEGIN RAISE EXCEPTION 'removal insert refused'; END $$;"
                " CREATE TRIGGER refuse_removal BEFORE INSERT ON file_removals"
                " FOR EACH ROW EXECUTE FUNCTION refuse_removal();"
            )
        )
    yield
    with engine.begin() as connection:
        connection.execute(
            text(
                "DROP TRIGGER refuse_removal ON file_removals;"
                " DROP FUNCTION refuse_removal();"
            )
        )


def _denied(caplog: pytest.LogCaptureFixture) -> int:
    return sum(r.getMessage() == "BookAccessDenied" for r in caplog.records)


def test_s9_ac1_ana_deletes_her_ready_book_and_it_leaves_her_list(
    client: TestClient,
    engine: Engine,
    jobs: ConversionJobs,
    signed_in_ana: str,
) -> None:
    book = upload(client, "dune.epub", DUNE)
    jobs.poll()

    response = client.delete(f"/api/books/{book['id']}")

    assert response.status_code == 204
    assert client.get("/api/books").json() == []
    assert events(engine, book["id"])[-1] == "book_deleted"
    assert library_bytes(engine, signed_in_ana) == (0, 0)
    assert client.delete(f"/api/books/{book['id']}").status_code == 404
    assert library_bytes(engine, signed_in_ana) == (0, 0)


def test_s9_ac2_a_processing_book_goes_and_its_conversion_never_runs(
    client: TestClient,
    engine: Engine,
    jobs: ConversionJobs,
    removals: FileRemoval,
    signed_in_ana: str,
    tmp_path: Path,
) -> None:
    book = upload(client, "dune.epub", DUNE)

    response = client.delete(f"/api/books/{book['id']}")

    assert response.status_code == 204
    assert client.get("/api/books").json() == []
    assert events(engine, book["id"])[-1] == "book_deleted_during_conversion"
    assert jobs.poll() == 0
    removals.poll()
    assert "book_ready" not in events(engine, book["id"])
    assert count(engine, "books") == 0
    assert stored_files(tmp_path) == []


def test_s9_ac3_ben_gets_404_for_anas_book_and_the_book_stays(
    client: TestClient,
    engine: Engine,
    jobs: ConversionJobs,
    signed_in_ana: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    book = upload(client, "dune.epub", DUNE)
    jobs.poll()
    assert sign_up(client, "ben@example.com") == 201
    assert sign_in(client, "ben@example.com") == 204

    foreign = client.delete(f"/api/books/{book['id']}")
    missing = client.delete(f"/api/books/{uuid.uuid4()}")

    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json() == {"code": "book_not_found"}
    assert _denied(caplog) == 1
    assert count(engine, "books") == 1
    assert "book_deleted" not in events(engine, book["id"])
    assert library_bytes(engine, signed_in_ana) == (len(DUNE), len(DUNE))


def test_bytes_used_equals_the_sum_of_the_book_sizes_after_a_delete(
    client: TestClient, engine: Engine, signed_in_ana: str
) -> None:
    dune = upload(client, "dune.epub", DUNE)
    upload(client, "emma.pdf", EMMA)

    assert client.delete(f"/api/books/{dune['id']}").status_code == 204

    assert library_bytes(engine, signed_in_ana) == (len(EMMA), len(EMMA))


def test_a_delete_that_cannot_queue_p4_keeps_the_book_and_its_bytes(
    client: TestClient,
    engine: Engine,
    signed_in_ana: str,
    failing_removal_insert: None,
) -> None:
    book = upload(client, "dune.epub", DUNE)

    with pytest.raises(DBAPIError):
        client.delete(f"/api/books/{book['id']}")

    assert [b["id"] for b in client.get("/api/books").json()] == [book["id"]]
    assert library_bytes(engine, signed_in_ana) == (len(DUNE), len(DUNE))
    assert "book_deleted_during_conversion" not in events(engine, book["id"])
