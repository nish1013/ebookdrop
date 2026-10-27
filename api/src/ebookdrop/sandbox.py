"""One locked-down Docker container per untrusted file."""

import shutil
import subprocess

SANDBOX_IMAGE = "ebookdrop-sandbox"


def sandbox_command(name: str, image: str, *, verb: str = "run") -> list[str]:
    """The `docker <verb>` line of one sandbox container, ending with the image."""
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
        image,
    ]


def docker() -> str:
    """The path of the docker client."""
    return shutil.which("docker") or "docker"


def remove(name: str) -> None:
    """Remove the container `name`, also when it still runs."""
    subprocess.run(  # noqa: S603
        [docker(), "rm", "-f", name], capture_output=True, check=False
    )
