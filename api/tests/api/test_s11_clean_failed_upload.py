import io
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from ebookdrop.conversion.port import (
    Conversion,
    ConversionFailedError,
    ConverterPort,
    Failure,
)
from ebookdrop.library.conversion_jobs import ConversionJobs
from ebookdrop.library.file_removal import FileRemoval
from ebookdrop.storage import LocalDiskStorage
from tests.api.conftest import events, upload
from tests.api.test_upload_storage import stored_files
from tests.conftest import FakeClock
from tests.samples import pdf

BAD = pdf(title="Bad")
TEN = datetime(2026, 10, 27, 10, 0, tzinfo=UTC)


class MalformedConverter:
    def convert(self, source: Path, work_dir: Path) -> Conversion:
        raise ConversionFailedError(Failure.MALFORMED)


@pytest.fixture
def converter() -> ConverterPort:
    return MalformedConverter()


def test_s11_ac1_p5_removes_the_file_of_an_upload_failed_8_days_ago(
    client: TestClient,
    engine: Engine,
    jobs: ConversionJobs,
    clock: FakeClock,
    removals: FileRemoval,
    signed_in_ana: str,
    tmp_path: Path,
) -> None:
    clock.current = TEN
    book = upload(client, "bad.pdf", BAD)
    jobs.poll()
    clock.advance(timedelta(days=7))
    assert removals.clean_failed() == 0
    assert stored_files(tmp_path) == [f"books/{book['id']}/original"]
    clock.advance(timedelta(days=1))

    assert removals.clean_failed() == 1

    assert stored_files(tmp_path) == []
    [listed] = client.get("/api/books").json()
    assert (listed["id"], listed["status"]) == (book["id"], "failed")
    assert events(engine, book["id"])[-1] == "failed_upload_cleaned_up"
    assert removals.clean_failed() == 0
    assert events(engine, book["id"]).count("failed_upload_cleaned_up") == 1


def test_staging_sweep_removes_staging_files_older_than_1_day(
    clock: FakeClock,
    storage: LocalDiskStorage,
    removals: FileRemoval,
    tmp_path: Path,
) -> None:
    for key, age in (
        ("staging/old/book.epub", timedelta(days=1, minutes=1)),
        ("staging/new/book.epub", timedelta(hours=23)),
        ("books/kept/original", timedelta(days=30)),
    ):
        storage.save(key, io.BytesIO(b"x"))
        at = (clock.now() - age).timestamp()
        os.utime(tmp_path / "storage" / key, (at, at))

    assert removals.sweep_staging() == 1

    assert stored_files(tmp_path) == ["books/kept/original", "staging/new/book.epub"]
    assert not (tmp_path / "storage" / "staging" / "old").exists()


def test_p5_removes_a_book_file_that_a_crash_left_on_a_failed_book(
    client: TestClient,
    jobs: ConversionJobs,
    clock: FakeClock,
    removals: FileRemoval,
    storage: LocalDiskStorage,
    signed_in_ana: str,
    tmp_path: Path,
) -> None:
    book = upload(client, "bad.pdf", BAD)
    jobs.poll()
    storage.save(f"books/{book['id']}/book.pdf", io.BytesIO(b"moved before a crash"))
    clock.advance(timedelta(days=8))

    assert removals.clean_failed() == 1

    assert stored_files(tmp_path) == []
