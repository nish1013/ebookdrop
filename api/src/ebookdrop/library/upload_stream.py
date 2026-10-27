"""Streams a multipart upload to a work file under a byte limit (decision 20)."""

from pathlib import Path
from typing import BinaryIO

from starlette.requests import Request

from ebookdrop.library.domain import MAX_FILE_BYTES, ReceivedFile

MULTIPART_OVERHEAD = 64 * 1024


class UploadSink:
    """Writes the file part, counts and hashes its bytes, and stops past `limit`."""

    def __init__(self, target: BinaryIO, limit: int = MAX_FILE_BYTES) -> None:
        self._target = target
        self._limit = limit
        self.size = 0

    def write(self, data: bytes) -> None:
        """Add `data`. Raise `UploadRejectedError(too_large)` past the limit."""
        raise NotImplementedError

    @property
    def sha256(self) -> str:
        """The hex sha256 of the bytes written so far."""
        raise NotImplementedError


def declared_too_large(request: Request) -> bool:
    """Say if the Content-Length alone breaks the limit."""
    return False


async def receive_upload(request: Request, work_dir: Path) -> ReceivedFile:
    """Read the `file` part of the body into `work_dir`."""
    raise NotImplementedError
