"""The Docker adapter of `ConverterPort`: one locked-down container per job."""

from pathlib import Path

from ebookdrop.conversion.port import CONVERT_SECONDS, Conversion
from ebookdrop.sandbox import SANDBOX_IMAGE, sandbox_command

NAME_PREFIX = "ebookdrop-convert-"


def convert_command(name: str, image: str) -> list[str]:
    """The `docker run` line of one convert container."""
    return sandbox_command(name, image)


class DockerConverter:
    """Runs `sandbox_convert` in a container with no network and tight limits."""

    def __init__(
        self, image: str = SANDBOX_IMAGE, timeout: float = CONVERT_SECONDS
    ) -> None:
        self._image = image
        self._timeout = timeout

    def convert(self, source: Path, work_dir: Path) -> Conversion:
        """Pipe `source` to a new container and unpack its output."""
        raise NotImplementedError
