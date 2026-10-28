"""The converter port and its result."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

CONVERT_SECONDS = 60.0


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


class Failure(StrEnum):
    """Why a conversion fails (`ConversionFailed`)."""

    MALFORMED = "malformed"
    UNREADABLE = "unreadable"
    TIMED_OUT = "timed_out"
    CRASHED = "crashed"


class ConversionError(Exception):
    """Root of the conversion errors."""


class ConversionFailedError(ConversionError):
    """The file did not become a readable book. The failure names why."""

    def __init__(self, failure: Failure) -> None:
        super().__init__(failure.value)
        self.failure = failure


class SandboxEscapeError(ConversionFailedError):
    """The conversion tried to open a network socket, and the sandbox killed it."""

    def __init__(self) -> None:
        super().__init__(Failure.CRASHED)


class ConverterUnavailableError(ConversionError):
    """The sandbox did not run, so the file has no result."""


class ConverterPort(Protocol):
    """Makes one uploaded file readable. Writes its output under `work_dir`."""

    def convert(self, source: Path, work_dir: Path) -> Conversion:
        """Convert `source` and return the result.

        Raise `ConversionFailedError` or `ConverterUnavailableError`.
        """
        ...
