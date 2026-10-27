"""File storage behind a port, with a local disk adapter."""

import shutil
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol


class StoragePort(Protocol):
    """Stores files by key. A key is a relative path such as `books/<id>/original`."""

    def save(self, key: str, source: BinaryIO) -> None:
        """Write the bytes of `source` to `key`, replacing any file there."""
        ...

    def open(self, key: str) -> BinaryIO:
        """Open the file at `key` for reading. Raise `FileNotFoundError` when absent."""
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

    def _path(self, key: str) -> Path:
        parts = PurePosixPath(key).parts
        if not parts or key.startswith("/") or ".." in parts or "\\" in key:
            raise InvalidKeyError(key)
        return self._root.joinpath(*parts)
