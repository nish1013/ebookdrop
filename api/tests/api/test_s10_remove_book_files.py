from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from ebookdrop.app import file_removal
from ebookdrop.conversion.port import ConverterPort
from ebookdrop.library.conversion_jobs import ConversionJobs
from ebookdrop.library.file_removal import FileRemoval
from ebookdrop.storage import LocalDiskStorage
from tests.api.conftest import events, upload
from tests.api.test_s6_mark_book_ready import DuneConverter
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
    assert removals.poll() == 1
    assert stored_files(tmp_path) == []
