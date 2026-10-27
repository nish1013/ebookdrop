import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from ebookdrop.library.conversion_jobs import ConversionJobs
from ebookdrop.library.metrics import (
    DailyShare,
    LateBook,
    MetricReader,
    RejectCount,
)
from tests.api.conftest import upload
from tests.conftest import FakeClock
from tests.samples import epub

TEN = datetime(2026, 10, 27, 10, 0, tzinfo=UTC)


def test_s6_ac3_a_book_ready_at_10_02_30_is_late_in_the_report(
    client: TestClient,
    engine: Engine,
    jobs: ConversionJobs,
    clock: FakeClock,
    signed_in_ana: str,
) -> None:
    clock.current = TEN
    dune = upload(client, "dune.epub", epub())
    clock.advance(timedelta(seconds=30))
    upload(client, "emma.epub", epub(padding=64, seed=1))
    clock.current = TEN + timedelta(minutes=2, seconds=30)

    assert jobs.poll() == 2

    report = MetricReader(engine).report()
    assert report.late == [
        LateBook(uuid.UUID(str(dune["id"])), TEN, TEN + timedelta(seconds=150))
    ]
    assert report.days == [DailyShare(date(2026, 10, 27), 2, 1, Decimal("50.0"), 0)]


def _book_events(engine: Engine, rows: list[tuple[uuid.UUID, str, datetime]]) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO book_events (book_id, name, at) VALUES (:b, :n, :at)"),
            [{"b": b, "n": n, "at": at} for b, n, at in rows],
        )


def _intake_events(
    engine: Engine, rows: list[tuple[str, str | None, datetime]]
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO intake_events (reader_id, name, reason, at)"
                " VALUES (:r, :n, :reason, :at)"
            ),
            [
                {"r": uuid.uuid4(), "n": n, "reason": reason, "at": at}
                for n, reason, at in rows
            ],
        )


def _received(engine: Engine, at: datetime, ready_after: timedelta | None) -> uuid.UUID:
    book_id = uuid.uuid4()
    rows = [(book_id, "upload_received", at)]
    if ready_after is None:
        rows.append((book_id, "conversion_failed", at + timedelta(seconds=30)))
    else:
        rows.append((book_id, "book_ready", at + ready_after))
    _book_events(engine, rows)
    return book_id


def test_s6_ac5_96_of_100_ready_in_time_and_7_rejects_by_reason(
    engine: Engine,
) -> None:
    minute = timedelta(minutes=1)
    for n in range(95):
        _received(engine, TEN + n * minute, minute)
    _received(engine, TEN + 95 * minute, 2 * minute)
    late = _received(engine, TEN + 96 * minute, 2 * minute + timedelta(seconds=1))
    _received(engine, TEN + 97 * minute, None)
    _received(engine, TEN + 98 * minute, None)
    _book_events(engine, [(uuid.uuid4(), "upload_received", TEN + 99 * minute)])
    _book_events(engine, [(uuid.uuid4(), "book_open_failed", TEN + 2 * minute)])
    day_before = datetime(2026, 10, 26, 23, 59, 50, tzinfo=UTC)
    _received(engine, day_before, timedelta(seconds=40))
    _intake_events(
        engine,
        [("upload_rejected", "not_epub_or_pdf", TEN)] * 4
        + [("upload_rejected", "too_large", TEN)] * 3
        + [("upload_rejected", "too_large", day_before)]
        + [("upload_abandoned", None, TEN), ("duplicate_upload_detected", None, TEN)],
    )

    report = MetricReader(engine).report()

    assert report.days == [
        DailyShare(date(2026, 10, 26), 1, 1, Decimal("100.0"), 0),
        DailyShare(date(2026, 10, 27), 100, 96, Decimal("96.0"), 1),
    ]
    assert [book.book_id for book in report.late] == [late]
    assert report.rejects == [
        RejectCount(date(2026, 10, 26), "too_large", 1),
        RejectCount(date(2026, 10, 27), "not_epub_or_pdf", 4),
        RejectCount(date(2026, 10, 27), "too_large", 3),
    ]
