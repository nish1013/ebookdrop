"""The Docker adapter of `InspectorPort`: one locked-down container per file."""

from pathlib import Path

from ebookdrop.conversion.port import BookFormat
from ebookdrop.inspection.port import INSPECT_SECONDS

INSPECT_IMAGE = "ebookdrop-inspect"


def sandbox_command(name: str, image: str) -> list[str]:
    """The `docker run` line of one inspect container, ending with the image."""
    raise NotImplementedError


class DockerInspector:
    """Runs `sandbox_check` in a container with no network and tight limits."""

    def __init__(
        self, image: str = INSPECT_IMAGE, timeout: float = INSPECT_SECONDS
    ) -> None:
        self._image = image
        self._timeout = timeout

    def inspect(self, source: Path) -> BookFormat:
        """Pipe `source` to a new container and read its verdict."""
        raise NotImplementedError
