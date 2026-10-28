"""Streams a multipart upload to a work file under a byte limit (decision 20)."""

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO

from python_multipart.multipart import MultipartParser, parse_options_header
from starlette.requests import Request

from ebookdrop.library.domain import (
    MAX_FILE_BYTES,
    InvalidUploadError,
    ReceivedFile,
    RejectReason,
    UploadRejectedError,
)

if TYPE_CHECKING:
    from python_multipart.multipart import MultipartCallbacks

MULTIPART_OVERHEAD = 64 * 1024
FILE_FIELD = b"file"


class UploadSink:
    """Writes the file part, counts and hashes its bytes, and stops past `limit`."""

    def __init__(self, target: BinaryIO, limit: int = MAX_FILE_BYTES) -> None:
        self._target = target
        self._limit = limit
        self._hash = hashlib.sha256()
        self.size = 0

    def write(self, data: bytes) -> None:
        """Add `data`. Raise `UploadRejectedError(too_large)` past the limit."""
        self.size += len(data)
        if self.size > self._limit:
            raise UploadRejectedError(RejectReason.TOO_LARGE)
        self._hash.update(data)
        self._target.write(data)

    @property
    def sha256(self) -> str:
        """The hex sha256 of the bytes written so far."""
        return self._hash.hexdigest()


def declared_too_large(request: Request) -> bool:
    """Say if the Content-Length alone breaks the limit."""
    declared = request.headers.get("content-length", "")
    return declared.isdigit() and int(declared) > MAX_FILE_BYTES + MULTIPART_OVERHEAD


async def receive_upload(request: Request, work_dir: Path) -> ReceivedFile:
    """Read the first `file` part of the body into `work_dir`.

    Raise `UploadRejectedError(too_large)` at the first byte past the limit, and
    `InvalidUploadError` when the body ends before the part does.
    """
    path = work_dir / "upload"
    with path.open("wb") as target:
        part = _FilePart(UploadSink(target))
        parser = MultipartParser(_boundary(request), part.callbacks())
        body = 0
        async for chunk in request.stream():
            body += len(chunk)
            if body > MAX_FILE_BYTES + MULTIPART_OVERHEAD:
                raise UploadRejectedError(RejectReason.TOO_LARGE)
            parser.write(chunk)
            if part.complete:
                break
    if not part.complete:
        raise InvalidUploadError
    return ReceivedFile(part.file_name, path, part.sink.size, part.sink.sha256)


class _FilePart:
    def __init__(self, sink: UploadSink) -> None:
        self.sink = sink
        self.file_name: str | None = None
        self.complete = False
        self._header = b""
        self._value = b""
        self._disposition = b""
        self._current = False
        self._found = False

    def callbacks(self) -> "MultipartCallbacks":
        return {
            "on_part_begin": self._begin,
            "on_header_field": self._header_field,
            "on_header_value": self._header_value,
            "on_header_end": self._header_end,
            "on_headers_finished": self._headers_finished,
            "on_part_data": self._data,
            "on_part_end": self._end,
        }

    def _begin(self) -> None:
        self._disposition = b""
        self._current = False

    def _header_field(self, data: bytes, start: int, end: int) -> None:
        self._header += data[start:end]

    def _header_value(self, data: bytes, start: int, end: int) -> None:
        self._value += data[start:end]

    def _header_end(self) -> None:
        if self._header.lower() == b"content-disposition":
            self._disposition = self._value
        self._header = self._value = b""

    def _headers_finished(self) -> None:
        _, options = parse_options_header(self._disposition)
        if options.get(b"name") != FILE_FIELD or self._found:
            return
        self._current = self._found = True
        raw = options.get(b"filename")
        self.file_name = raw.decode(errors="replace") if raw is not None else None

    def _data(self, data: bytes, start: int, end: int) -> None:
        if self._current:
            self.sink.write(data[start:end])

    def _end(self) -> None:
        if self._current:
            self.complete = True
            self._current = False


def _boundary(request: Request) -> bytes:
    kind, options = parse_options_header(request.headers.get("content-type", ""))
    boundary = options.get(b"boundary")
    if kind != b"multipart/form-data" or not boundary:
        raise InvalidUploadError
    return boundary
