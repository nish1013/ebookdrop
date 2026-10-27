"""The Docker adapter of `InspectorPort`: one locked-down container per file."""

import shutil
import subprocess
import uuid
from collections.abc import Callable
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

Runner = Callable[..., subprocess.CompletedProcess[bytes]]

INSPECT_IMAGE = "ebookdrop-inspect"
NAME_PREFIX = "ebookdrop-inspect-"
START_SECONDS = 30.0
# 137 is a kill by the memory limit. The docker client itself exits 1 or 125-127.
_DAMAGED_EXITS = {CRASH_EXIT, 137}


def sandbox_command(name: str, image: str) -> list[str]:
    """The `docker create` line of one inspect container, ending with the image."""
    return [
        _docker(),
        "create",
        "--rm",
        "-i",
        "--pull",
        "never",
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
        self,
        image: str = INSPECT_IMAGE,
        timeout: float = INSPECT_SECONDS,
        run: Runner = subprocess.run,
    ) -> None:
        self._image = image
        self._timeout = timeout
        self._run = run

    def inspect(self, source: Path) -> BookFormat:
        """Start a new container, pipe `source` to it and read its verdict.

        The time limit starts when the container runs. A run past it refuses
        the file as damaged (a zip bomb). A container that does not start
        gives no verdict.
        """
        name = f"{NAME_PREFIX}{uuid.uuid4().hex}"
        self._start(name)
        try:
            with source.open("rb") as stdin:
                done = self._run(
                    [_docker(), "attach", name],
                    stdin=stdin,
                    capture_output=True,
                    timeout=self._timeout,
                    check=False,
                )
        except subprocess.TimeoutExpired:
            self._remove(name)
            raise FileRefusedError(Refusal.DAMAGED) from None
        except OSError as err:
            self._remove(name)
            raise InspectorUnavailableError("docker did not attach") from err
        if done.returncode in _DAMAGED_EXITS:
            raise FileRefusedError(Refusal.DAMAGED)
        if done.returncode != 0:
            raise InspectorUnavailableError(f"docker exit {done.returncode}")
        return read_verdict(done.stdout.decode(errors="replace"))

    def _start(self, name: str) -> None:
        # The started container blocks on stdin until the attach sends the file.
        for command in (sandbox_command(name, self._image), [_docker(), "start", name]):
            try:
                done = self._run(
                    command, capture_output=True, timeout=START_SECONDS, check=False
                )
            except (subprocess.TimeoutExpired, OSError) as err:
                self._remove(name)
                raise InspectorUnavailableError("docker did not start") from err
            if done.returncode != 0:
                self._remove(name)
                raise InspectorUnavailableError(f"docker exit {done.returncode}")

    def _remove(self, name: str) -> None:
        self._run([_docker(), "rm", "-f", name], capture_output=True, check=False)


def _docker() -> str:
    return shutil.which("docker") or "docker"
