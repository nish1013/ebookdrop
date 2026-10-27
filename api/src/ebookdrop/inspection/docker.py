"""The Docker adapter of `InspectorPort`: one locked-down container per file."""

import shutil
import subprocess
import uuid
from pathlib import Path

from ebookdrop.conversion.port import BookFormat
from ebookdrop.inspection.port import (
    INSPECT_SECONDS,
    FileRefusedError,
    InspectorUnavailableError,
    Refusal,
    read_verdict,
)
from ebookdrop.inspection.sandbox_check import CRASH_EXIT

INSPECT_IMAGE = "ebookdrop-inspect"
NAME_PREFIX = "ebookdrop-inspect-"
# 137 is a kill by the memory limit. The docker client itself exits 1 or 125-127.
_DAMAGED_EXITS = {CRASH_EXIT, 137}


def sandbox_command(name: str, image: str) -> list[str]:
    """The `docker run` line of one inspect container, ending with the image."""
    return [
        _docker(),
        "run",
        "--rm",
        "-i",
        "--name",
        name,
        "--network",
        "none",
        "--read-only",
        "--memory",
        "512m",
        "--memory-swap",
        "512m",
        "--pids-limit",
        "64",
        "--cpus",
        "1",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--user",
        "65534:65534",
        image,
    ]


class DockerInspector:
    """Runs `sandbox_check` in a container with no network and tight limits."""

    def __init__(
        self, image: str = INSPECT_IMAGE, timeout: float = INSPECT_SECONDS
    ) -> None:
        self._image = image
        self._timeout = timeout

    def inspect(self, source: Path) -> BookFormat:
        """Pipe `source` to a new container and read its verdict.

        A run past the time limit refuses the file as damaged (a zip bomb).
        """
        name = f"{NAME_PREFIX}{uuid.uuid4().hex}"
        try:
            with source.open("rb") as stdin:
                done = subprocess.run(  # noqa: S603
                    sandbox_command(name, self._image),
                    stdin=stdin,
                    capture_output=True,
                    timeout=self._timeout,
                    check=False,
                )
        except subprocess.TimeoutExpired:
            _remove(name)
            raise FileRefusedError(Refusal.DAMAGED) from None
        except OSError as err:
            raise InspectorUnavailableError("docker did not start") from err
        if done.returncode in _DAMAGED_EXITS:
            raise FileRefusedError(Refusal.DAMAGED)
        if done.returncode != 0:
            raise InspectorUnavailableError(f"docker exit {done.returncode}")
        return read_verdict(done.stdout.decode(errors="replace"))


def _docker() -> str:
    return shutil.which("docker") or "docker"


def _remove(name: str) -> None:
    subprocess.run(  # noqa: S603
        [_docker(), "rm", "-f", name], capture_output=True, check=False
    )
