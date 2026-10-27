from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from ebookdrop.storage import LocalDiskStorage
from tests.api.conftest import events, upload
from tests.samples import epub

DUNE = epub(padding=2 * 1024 * 1024)


def test_s4_ac1_upload_shows_the_file_as_processing(
    client: TestClient, engine: Engine, signed_in_ana: str
) -> None:
    book = upload(client, "dune.epub", DUNE)

    assert book["title"] == "dune.epub"
    assert book["status"] == "processing"
    assert client.get("/api/books").json() == [book]
    assert events(engine, book["id"]) == ["upload_received", "conversion_queued"]


def test_s4_ac7_signed_out_upload_gets_401_and_no_event(
    client: TestClient, engine: Engine, storage: LocalDiskStorage
) -> None:
    response = client.post("/api/books", files={"file": ("dune.epub", DUNE)})

    assert response.status_code == 401
    assert response.json() == {"code": "signed_out"}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM books")).scalar() == 0
        assert (
            connection.execute(text("SELECT count(*) FROM book_events")).scalar() == 0
        )
