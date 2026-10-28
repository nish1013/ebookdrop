import os
import subprocess
import threading
from pathlib import Path

import pytest

from ebookdrop.conversion import docker as docker_module
from ebookdrop.conversion.docker import DockerConverter
from ebookdrop.conversion.port import (
    ConversionFailedError,
    ConverterUnavailableError,
    Failure,
)
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


def test_convert_whose_container_starts_slowly_is_unavailable_not_timed_out(
    book: Path, tmp_path: Path
) -> None:
    docker = FakeDocker(slow_start=True)

    with pytest.raises(ConverterUnavailableError):
        DockerConverter(run=docker).convert(book, tmp_path)

    assert docker.verbs[-1] == "rm"


class _FloodingDocker:
    """Floods the attach output. Like the daemon, `rm` waits for it to drain."""

    def __init__(self) -> None:
        self.drained = threading.Event()
        self.rm_saw_drain = False

    def __call__(
        self, args: list[str], *, stdout: object = None, **_: object
    ) -> subprocess.CompletedProcess[bytes]:
        verb = args[1]
        if verb == "attach" and isinstance(stdout, int):
            block = b"\0" * 64 * 1024
            for _ in range(64):
                view = memoryview(block)
                while view:
                    view = view[os.write(stdout, view) :]
            self.drained.set()
        if verb == "rm":
            self.rm_saw_drain = self.drained.wait(timeout=5)
        return subprocess.CompletedProcess(args, 0, b"", b"")


def test_convert_output_past_its_cap_keeps_draining_while_the_container_is_removed(
    book: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(docker_module, "_MAX_OUTPUT", 1024)
    docker = _FloodingDocker()

    with pytest.raises(ConversionFailedError) as failed:
        DockerConverter(run=docker).convert(book, tmp_path)

    assert failed.value.failure == Failure.CRASHED
    assert docker.rm_saw_drain
