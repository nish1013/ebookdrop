import uuid

from fastapi.testclient import TestClient

from ebookdrop.library.conversion_jobs import ConversionJobs
from tests.api.conftest import sign_in, sign_up, upload
from tests.samples import epub

DUNE = epub()


def test_library_lists_the_readers_own_books_only(
    client: TestClient, signed_in_ana: str
) -> None:
    upload(client, "dune.epub", DUNE)
    assert sign_up(client, "ben@example.com") == 201
    assert sign_in(client, "ben@example.com") == 204

    assert client.get("/api/books").json() == []


def test_cover_of_a_foreign_book_answers_like_a_missing_book(
    client: TestClient, jobs: ConversionJobs, signed_in_ana: str
) -> None:
    book = upload(client, "dune.epub", DUNE)
    jobs.poll()
    assert sign_up(client, "ben@example.com") == 201
    assert sign_in(client, "ben@example.com") == 204

    foreign = client.get(f"/api/books/{book['id']}/cover")
    missing = client.get(f"/api/books/{uuid.uuid4()}/cover")

    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json() == {"code": "book_not_found"}


def test_signed_out_library_list_gets_401(client: TestClient) -> None:
    response = client.get("/api/books")

    assert response.status_code == 401
    assert response.json() == {"code": "signed_out"}
