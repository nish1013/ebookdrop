"""File storage behind a port, with a local disk adapter."""

import contextlib
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol


@dataclass(frozen=True)
class StoredFile:
    """One stored file and the time of its last write."""

    key: str
    modified_at: datetime


class StoragePort(Protocol):
    """Stores files by key. A key is a relative path such as `books/<id>/original`."""

    def save(self, key: str, source: BinaryIO) -> None:
        """Write the bytes of `source` to `key`, replacing any file there."""
        ...

    def open(self, key: str) -> BinaryIO:
        """Open the file at `key` for reading. Raise `FileNotFoundError` when absent."""
        ...

    def delete(self, key: str) -> None:
        """Remove the file at `key`. A missing file is no error."""
        ...

    def move(self, source: str, target: str) -> None:
        """Move the file at `source` to `target`, replacing any file there."""
        ...

    def files(self, area: str) -> list[StoredFile]:
        """List every file under the area `area`, such as `staging`."""
        ...


class InvalidKeyError(ValueError):
    """The key leaves the storage root or is not relative."""


class LocalDiskStorage:
    """Stores files under one folder on the local disk."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def save(self, key: str, source: BinaryIO) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as target:
            shutil.copyfileobj(source, target)

    def open(self, key: str) -> BinaryIO:
        return self._path(key).open("rb")

    def delete(self, key: str) -> None:
        path = self._path(key)
        path.unlink(missing_ok=True)
        with contextlib.suppress(OSError):
            path.parent.rmdir()

    def move(self, source: str, target: str) -> None:
        path = self._path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path(source).replace(path)

    def files(self, area: str) -> list[StoredFile]:
        root = self._path(area)
        if not root.is_dir():
            return []
        found: list[StoredFile] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                modified = path.stat().st_mtime
            except FileNotFoundError:
                continue
            key = path.relative_to(self._root).as_posix()
            found.append(StoredFile(key, datetime.fromtimestamp(modified, UTC)))
        return found

    def _path(self, key: str) -> Path:
        parts = PurePosixPath(key).parts
        if not parts or key.startswith("/") or ".." in parts or "\\" in key:
            raise InvalidKeyError(key)
        return self._root.joinpath(*parts)
