"""The Docker adapter of `InspectorPort`: one locked-down container per file."""

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
from ebookdrop.sandbox import (
    SANDBOX_IMAGE,
    Runner,
    SandboxNotStartedError,
    docker,
    remove,
    sandbox_command,
    start,
)

NAME_PREFIX = "ebookdrop-inspect-"
# 137 is a kill by the memory limit. The docker client itself exits 1 or 125-127.
_DAMAGED_EXITS = {CRASH_EXIT, 137}


class DockerInspector:
    """Runs `sandbox_check` in a container with no network and tight limits."""

    def __init__(
        self,
        image: str = SANDBOX_IMAGE,
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
        try:
            start(name, sandbox_command(name, self._image, verb="create"), self._run)
        except SandboxNotStartedError as err:
            raise InspectorUnavailableError(str(err)) from err
        try:
            with source.open("rb") as stdin:
                done = self._run(
                    [docker(), "attach", name],
                    stdin=stdin,
                    capture_output=True,
                    timeout=self._timeout,
                    check=False,
                )
        except subprocess.TimeoutExpired:
            remove(name, self._run)
            raise FileRefusedError(Refusal.DAMAGED) from None
        except OSError as err:
            remove(name, self._run)
            raise InspectorUnavailableError("docker did not attach") from err
        if done.returncode in _DAMAGED_EXITS:
            raise FileRefusedError(Refusal.DAMAGED)
        if done.returncode != 0:
            raise InspectorUnavailableError(f"docker exit {done.returncode}")
        return read_verdict(done.stdout.decode(errors="replace"))
