"""The converter port and its result."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol


class BookFormat(StrEnum):
    """The format of a readable book."""

    EPUB = "epub"
    PDF = "pdf"


@dataclass(frozen=True)
class Conversion:
    """A converted book. The cover, when present, is a PNG file."""

    format: BookFormat
    book: Path
    title: str | None
    author: str | None
    cover: Path | None


class ConverterPort(Protocol):
    """Makes one uploaded file readable. Writes its output under `work_dir`."""

    def convert(self, source: Path, work_dir: Path) -> Conversion:
        """Convert `source` and return the result."""
        ...
