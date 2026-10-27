from pathlib import Path

import pytest

from ebookdrop.conversion.port import BookFormat
from ebookdrop.inspection.docker import DockerInspector
from ebookdrop.inspection.port import (
    FileRefusedError,
    InspectorUnavailableError,
    Refusal,
)
from tests.fakes import FakeDocker


@pytest.fixture
def book(tmp_path: Path) -> Path:
    path = tmp_path / "dune.epub"
    path.write_bytes(b"book bytes")
    return path


def test_inspect_reads_the_verdict_of_the_container(book: Path) -> None:
    assert DockerInspector(run=FakeDocker()).inspect(book) == BookFormat.EPUB


def test_inspect_whose_container_starts_slowly_is_unavailable_not_damaged(
    book: Path,
) -> None:
    docker = FakeDocker(slow_start=True)

    with pytest.raises(InspectorUnavailableError):
        DockerInspector(run=docker).inspect(book)

    assert docker.verbs[-1] == "rm"


def test_inspect_past_its_time_limit_is_damaged_and_removes_the_container(
    book: Path,
) -> None:
    docker = FakeDocker(slow_run=True)

    with pytest.raises(FileRefusedError) as refused:
        DockerInspector(run=docker).inspect(book)

    assert refused.value.refusal == Refusal.DAMAGED
    assert docker.verbs[-1] == "rm"
