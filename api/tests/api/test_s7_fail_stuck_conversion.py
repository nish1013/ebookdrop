from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from ebookdrop.library.conversion_jobs import ConversionJobs
from tests.api.conftest import events, upload
from tests.conftest import FakeClock
from tests.samples import epub

DUNE = epub()
TEN = datetime(2026, 10, 27, 10, 0, tzinfo=UTC)


def test_s7_ac1_a_book_processing_for_5_minutes_fails_as_stuck(
    client: TestClient,
    engine: Engine,
    jobs: ConversionJobs,
    clock: FakeClock,
    signed_in_ana: str,
) -> None:
    clock.current = TEN
    book = upload(client, "dune.epub", DUNE)
    clock.advance(timedelta(minutes=4, seconds=59))
    assert jobs.fail_stuck() == 0
    clock.advance(timedelta(seconds=1))

    assert jobs.fail_stuck() == 1

    [listed] = client.get("/api/books").json()
    assert (listed["status"], listed["failure"]) == ("failed", "stuck")
    clock.advance(timedelta(minutes=1))
    assert jobs.fail_stuck() == 0
    assert events(engine, book["id"]).count("conversion_failed") == 1


def test_s7_ac2_a_book_ready_at_10_00_40_stays_ready_past_the_deadline(
    client: TestClient,
    engine: Engine,
    jobs: ConversionJobs,
    clock: FakeClock,
    signed_in_ana: str,
) -> None:
    clock.current = TEN
    book = upload(client, "dune.epub", DUNE)
    clock.advance(timedelta(seconds=40))
    jobs.poll()
    clock.current = TEN + timedelta(minutes=5)

    assert jobs.fail_stuck() == 0

    [listed] = client.get("/api/books").json()
    assert (listed["status"], listed["failure"]) == ("ready", None)
    assert events(engine, book["id"])[-1] == "book_ready"


def test_r13_a_conversion_that_ends_after_the_stuck_fail_does_not_revive_it(
    client: TestClient,
    engine: Engine,
    jobs: ConversionJobs,
    clock: FakeClock,
    signed_in_ana: str,
) -> None:
    clock.current = TEN
    book = upload(client, "dune.epub", DUNE)
    clock.advance(timedelta(minutes=5))
    jobs.fail_stuck()

    jobs.poll()

    [listed] = client.get("/api/books").json()
    assert (listed["status"], listed["failure"]) == ("failed", "stuck")
    assert "book_ready" not in events(engine, book["id"])
