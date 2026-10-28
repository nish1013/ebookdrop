import io
import logging
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from ebookdrop.app import conversion_jobs, file_removal
from ebookdrop.conversion.port import Conversion, ConverterPort
from ebookdrop.library.conversion_jobs import ConversionJobs
from ebookdrop.library.file_removal import FileRemoval
from ebookdrop.storage import LocalDiskStorage
from tests.api.conftest import events, upload
from tests.api.test_s6_mark_book_ready import DeletedMeanwhileConverter, DuneConverter
from tests.api.test_upload_storage import stored_files
from tests.conftest import FakeClock
from tests.samples import epub

DUNE = epub(title="Dune")


class ProcessStoppedError(BaseException):
    """The worker process ends between two file removals."""


class StoppingStorage(LocalDiskStorage):
    """Stops the process at a given removal, as a kill or a power cut can."""

    def __init__(self, root: Path, stop_at: int, stop: BaseException) -> None:
        super().__init__(root)
        self._left = stop_at
        self._stop = stop

    def delete(self, key: str) -> None:
        self._left -= 1
        if self._left == 0:
            raise self._stop
        super().delete(key)


class FailingStorage(LocalDiskStorage):
    """Fails each removal of a file of the given books, as a broken disk can."""

    def __init__(self, root: Path, book_ids: set[str]) -> None:
        super().__init__(root)
        self._book_ids = book_ids
        self.attempts: list[str] = []

    def delete(self, key: str) -> None:
        book_id = key.split("/")[1]
        if book_id in self._book_ids:
            self.attempts.append(book_id)
            raise OSError("disk busy")
        super().delete(key)


@pytest.fixture
def converter() -> ConverterPort:
    return DuneConverter()


def _deleted_ready_book(client: TestClient, jobs: ConversionJobs) -> str:
    book = upload(client, "dune.epub", DUNE)
    jobs.poll()
    assert client.delete(f"/api/books/{book['id']}").status_code == 204
    return str(book["id"])


def test_s10_ac1_p4_removes_the_original_the_converted_file_and_the_cover(
    client: TestClient,
    engine: Engine,
    jobs: ConversionJobs,
    removals: FileRemoval,
    signed_in_ana: str,
    tmp_path: Path,
) -> None:
    book = upload(client, "dune.epub", DUNE)
    jobs.poll()
    assert stored_files(tmp_path) == [
        f"books/{book['id']}/book.epub",
        f"books/{book['id']}/cover.png",
        f"books/{book['id']}/original",
    ]
    assert client.delete(f"/api/books/{book['id']}").status_code == 204

    assert removals.poll() == 1

    assert stored_files(tmp_path) == []
    assert events(engine, book["id"]).count("book_files_removed") == 1
    assert removals.poll() == 0


def test_s10_ac2_p4_after_2_of_3_files_removes_the_third_with_one_event(
    client: TestClient,
    engine: Engine,
    jobs: ConversionJobs,
    clock: FakeClock,
    removals: FileRemoval,
    signed_in_ana: str,
    tmp_path: Path,
) -> None:
    book_id = _deleted_ready_book(client, jobs)
    stopping = StoppingStorage(tmp_path / "storage", 3, ProcessStoppedError())
    with pytest.raises(ProcessStoppedError):
        file_removal(engine, clock, stopping).poll()
    assert len(stored_files(tmp_path)) == 1

    assert removals.poll() == 1

    assert stored_files(tmp_path) == []
    assert events(engine, book_id).count("book_files_removed") == 1
    assert removals.poll() == 0


def test_p4_retries_a_removal_that_failed_until_it_is_done(
    client: TestClient,
    engine: Engine,
    jobs: ConversionJobs,
    clock: FakeClock,
    removals: FileRemoval,
    signed_in_ana: str,
    tmp_path: Path,
) -> None:
    book_id = _deleted_ready_book(client, jobs)
    failing = StoppingStorage(tmp_path / "storage", 1, OSError("disk busy"))

    assert file_removal(engine, clock, failing).poll() == 0

    assert "book_files_removed" not in events(engine, book_id)
    clock.advance(timedelta(hours=1))
    assert removals.poll() == 1
    assert stored_files(tmp_path) == []


def test_p4_removes_a_book_file_that_a_crash_left_on_a_book_with_no_format(
    client: TestClient,
    removals: FileRemoval,
    storage: LocalDiskStorage,
    signed_in_ana: str,
    tmp_path: Path,
) -> None:
    book = upload(client, "dune.epub", DUNE)
    storage.save(f"books/{book['id']}/book.epub", io.BytesIO(b"moved before a crash"))
    assert client.delete(f"/api/books/{book['id']}").status_code == 204

    assert removals.poll() == 1

    assert stored_files(tmp_path) == []


def test_p4_ten_removals_that_always_fail_do_not_block_an_eleventh(
    client: TestClient,
    engine: Engine,
    clock: FakeClock,
    signed_in_ana: str,
    tmp_path: Path,
) -> None:
    books = [
        str(upload(client, f"{n}.epub", epub(title=f"{n}"))["id"]) for n in range(11)
    ]
    for book_id in books:
        assert client.delete(f"/api/books/{book_id}").status_code == 204
        clock.advance(timedelta(milliseconds=1))
    failing = FailingStorage(tmp_path / "storage", set(books[:10]))
    removals = file_removal(engine, clock, failing)

    assert removals.poll() == 0
    clock.advance(timedelta(seconds=1))
    assert removals.poll() == 1

    assert "book_files_removed" in events(engine, books[10])
    assert stored_files(tmp_path) == sorted(
        f"books/{book_id}/original" for book_id in books[:10]
    )


def test_p4_waits_longer_after_each_failed_removal_and_logs_the_attempts(
    client: TestClient,
    engine: Engine,
    clock: FakeClock,
    signed_in_ana: str,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    book_id = _deleted_book(client)
    failing = FailingStorage(tmp_path / "storage", {book_id})
    removals = file_removal(engine, clock, failing)
    start = clock.now()
    tried_at: list[timedelta] = []

    with caplog.at_level(logging.WARNING):
        while len(tried_at) < 4 and clock.now() - start < timedelta(minutes=10):
            before = len(failing.attempts)
            removals.poll()
            if len(failing.attempts) > before:
                tried_at.append(clock.now() - start)
            clock.advance(timedelta(seconds=1))

    waits = [b - a for a, b in zip(tried_at, tried_at[1:], strict=False)]
    assert len(waits) == 3
    assert waits[0] < waits[1] < waits[2]
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert [getattr(r, "attempts", None) for r in warnings] == [1, 2, 3, 4]


class RemovedMeanwhileConverter(DeletedMeanwhileConverter):
    """Ana deletes the book while its conversion runs, and P4 runs at once."""

    def __init__(self, client: TestClient, removals: FileRemoval) -> None:
        super().__init__(client)
        self._removals = removals

    def convert(self, source: Path, work_dir: Path) -> Conversion:
        conversion = super().convert(source, work_dir)
        assert self._removals.poll() == 1
        return conversion


def test_a_book_deleted_while_processing_leaves_no_file_after_p4_and_its_conversion(
    client: TestClient,
    engine: Engine,
    clock: FakeClock,
    storage: LocalDiskStorage,
    removals: FileRemoval,
    signed_in_ana: str,
    tmp_path: Path,
) -> None:
    converter = RemovedMeanwhileConverter(client, removals)
    jobs = conversion_jobs(engine, clock, storage, converter)
    book = upload(client, "dune.epub", DUNE)
    converter.book_id = str(book["id"])

    assert jobs.poll() == 1

    assert removals.poll() == 0
    assert stored_files(tmp_path) == []
    assert events(engine, book["id"]).count("book_files_removed") == 1
    assert "book_ready" not in events(engine, book["id"])


def _deleted_book(client: TestClient) -> str:
    book = upload(client, "dune.epub", DUNE)
    assert client.delete(f"/api/books/{book['id']}").status_code == 204
    return str(book["id"])
