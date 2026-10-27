from pathlib import Path

import pytest

from ebookdrop.conversion.docker import DockerConverter
from ebookdrop.conversion.port import ConversionFailedError, Failure
from tests.fakes import FakeDocker


@pytest.fixture
def book(tmp_path: Path) -> Path:
    path = tmp_path / "dune.epub"
    path.write_bytes(b"book bytes")
    return path


@pytest.mark.parametrize("remove", ["hangs", "fails"])
def test_convert_result_stands_when_the_container_remove_goes_wrong(
    book: Path, tmp_path: Path, remove: str
) -> None:
    docker = FakeDocker(slow_run=True, remove=remove)

    with pytest.raises(ConversionFailedError) as failed:
        DockerConverter(run=docker).convert(book, tmp_path)

    assert failed.value.failure == Failure.TIMED_OUT
    assert docker.verbs[-1] == "rm"
