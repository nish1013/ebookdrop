"""One locked-down Docker container per untrusted file."""

import logging
import shutil
import subprocess
from collections.abc import Callable, Sequence

Runner = Callable[..., subprocess.CompletedProcess[bytes]]

SANDBOX_IMAGE = "ebookdrop-sandbox"
REMOVE_SECONDS = 10.0
_log = logging.getLogger(__name__)


def sandbox_command(
    name: str, image: str, options: Sequence[str] = (), *, verb: str = "run"
) -> list[str]:
    """The `docker <verb>` line of one sandbox container, ending with the image.

    `options` add to the limits. They never replace one.
    """
    return [
        docker(),
        verb,
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
        *options,
        image,
    ]


def docker() -> str:
    """The path of the docker client."""
    return shutil.which("docker") or "docker"


def remove(name: str, run: Runner = subprocess.run) -> None:
    """Remove the container `name`, also when it still runs.

    A remove that hangs or fails only logs, so the result of the job stands.
    """
    try:
        run(
            [docker(), "rm", "-f", name],
            capture_output=True,
            timeout=REMOVE_SECONDS,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        _log.warning("container %s was not removed", name)
