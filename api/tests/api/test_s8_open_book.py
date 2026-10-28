import logging
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from ebookdrop.library.conversion_jobs import ConversionJobs
from ebookdrop.library.metrics import MetricReader
from tests.api.conftest import events, reader_id, sign_in, sign_up, upload
from tests.conftest import FakeClock
from tests.samples import epub, pdf

DUNE = epub(title="Dune")
EMMA = pdf(title="Emma")


def denials(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.getMessage() == "BookAccessDenied"]


def test_s8_ac1_ana_opens_her_ready_epub(
    client: TestClient, jobs: ConversionJobs, signed_in_ana: str
) -> None:
    book = upload(client, "dune.epub", DUNE)
    jobs.poll()

    response = client.get(f"/api/books/{book['id']}/content")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/epub+zip"
    assert response.content == DUNE


def test_s8_ac1_ana_opens_her_ready_pdf(
    client: TestClient, jobs: ConversionJobs, signed_in_ana: str
) -> None:
    book = upload(client, "emma.pdf", EMMA)
    jobs.poll()

    response = client.get(f"/api/books/{book['id']}/content")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == EMMA


def test_s8_ac2_ben_gets_404_for_anas_book_like_a_missing_book(
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
    caplog.set_level(logging.INFO)

    missing = client.get(f"/api/books/{uuid.uuid4()}/content")
    assert denials(caplog) == []
    foreign = client.get(f"/api/books/{book['id']}/content")

    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json() == {"code": "book_not_found"}
    [denied] = denials(caplog)
    assert denied.__dict__["book_id"] == uuid.UUID(str(book["id"]))
    assert denied.__dict__["reader_id"] == reader_id(engine, "ben@example.com")


def test_s8_ac3_an_open_failure_is_counted_and_the_book_stays_ready(
    client: TestClient, engine: Engine, jobs: ConversionJobs, signed_in_ana: str
) -> None:
    book = upload(client, "dune.epub", DUNE)
    jobs.poll()

    response = client.post(f"/api/books/{book['id']}/open-failures")

    assert response.status_code == 204
    assert events(engine, book["id"])[-1] == "book_open_failed"
    assert [b["status"] for b in client.get("/api/books").json()] == ["ready"]
    assert [day.open_failures for day in MetricReader(engine).report().days] == [1]


def test_s8_ac3_open_failures_count_one_per_book_per_utc_day(
    client: TestClient,
    engine: Engine,
    clock: FakeClock,
    jobs: ConversionJobs,
    signed_in_ana: str,
) -> None:
    book = upload(client, "dune.epub", DUNE)
    jobs.poll()

    for _ in range(5):
        client.post(f"/api/books/{book['id']}/open-failures")
    clock.advance(timedelta(days=1))
    client.post(f"/api/books/{book['id']}/open-failures")

    assert [day.open_failures for day in MetricReader(engine).report().days] == [1, 1]
