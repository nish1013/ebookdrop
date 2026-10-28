import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from ebookdrop.library.conversion_jobs import ConversionJobs
from tests.api.conftest import events, sign_in, sign_up, upload
from tests.samples import epub

DUNE = epub()


def test_library_lists_the_readers_own_books_only(
    client: TestClient, signed_in_ana: str
) -> None:
    upload(client, "dune.epub", DUNE)
    assert sign_up(client, "ben@example.com") == 201
    assert sign_in(client, "ben@example.com") == 204

    assert client.get("/api/books").json() == []


def _denied(caplog: pytest.LogCaptureFixture) -> int:
    return sum(r.getMessage() == "BookAccessDenied" for r in caplog.records)


def _ben_signs_in(client: TestClient) -> None:
    assert sign_up(client, "ben@example.com") == 201
    assert sign_in(client, "ben@example.com") == 204


def test_cover_of_a_foreign_book_answers_like_a_missing_book(
    client: TestClient,
    jobs: ConversionJobs,
    signed_in_ana: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    book = upload(client, "dune.epub", DUNE)
    jobs.poll()
    _ben_signs_in(client)

    foreign = client.get(f"/api/books/{book['id']}/cover")
    missing = client.get(f"/api/books/{uuid.uuid4()}/cover")

    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json() == {"code": "book_not_found"}
    assert _denied(caplog) == 1


def test_signed_out_library_list_gets_401(client: TestClient) -> None:
    response = client.get("/api/books")

    assert response.status_code == 401
    assert response.json() == {"code": "signed_out"}


def test_book_content_carries_a_policy_that_runs_no_script(
    client: TestClient, jobs: ConversionJobs, signed_in_ana: str
) -> None:
    book = upload(client, "dune.epub", DUNE)
    jobs.poll()

    response = client.get(f"/api/books/{book['id']}/content")

    assert response.headers["content-security-policy"] == (
        "default-src 'none'; script-src 'none'; sandbox"
    )
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "private, no-store"


def test_content_of_a_processing_book_is_not_found_and_not_denied(
    client: TestClient, signed_in_ana: str, caplog: pytest.LogCaptureFixture
) -> None:
    book = upload(client, "dune.epub", DUNE)

    response = client.get(f"/api/books/{book['id']}/content")

    assert response.status_code == 404
    assert response.json() == {"code": "book_not_found"}
    assert _denied(caplog) == 0


def test_open_failure_of_a_foreign_book_answers_like_a_missing_book(
    client: TestClient,
    engine: Engine,
    jobs: ConversionJobs,
    signed_in_ana: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    book = upload(client, "dune.epub", DUNE)
    jobs.poll()
    before = events(engine, book["id"])
    _ben_signs_in(client)

    foreign = client.post(f"/api/books/{book['id']}/open-failures")
    missing = client.post(f"/api/books/{uuid.uuid4()}/open-failures")

    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json() == {"code": "book_not_found"}
    assert events(engine, book["id"]) == before
    assert _denied(caplog) == 1


def test_open_failure_of_a_processing_book_is_not_found(
    client: TestClient, engine: Engine, signed_in_ana: str
) -> None:
    book = upload(client, "dune.epub", DUNE)

    response = client.post(f"/api/books/{book['id']}/open-failures")

    assert response.status_code == 404
    assert "book_open_failed" not in events(engine, book["id"])


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "content"), ("POST", "open-failures")],
)
def test_signed_out_book_read_gets_401(
    client: TestClient, method: str, path: str
) -> None:
    response = client.request(method, f"/api/books/{uuid.uuid4()}/{path}")

    assert response.status_code == 401
    assert response.json() == {"code": "signed_out"}


def test_signed_out_book_delete_gets_401(client: TestClient) -> None:
    response = client.delete(f"/api/books/{uuid.uuid4()}")

    assert response.status_code == 401
    assert response.json() == {"code": "signed_out"}
