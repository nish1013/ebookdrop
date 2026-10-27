"""The inspector port, its refusals and its verdict words."""

from enum import StrEnum
from pathlib import Path
from typing import Protocol

from ebookdrop.conversion.port import BookFormat

INSPECT_SECONDS = 10.0


class Refusal(StrEnum):
    """Why an inspect refuses a file (decision 19)."""

    NOT_EPUB_OR_PDF = "not_epub_or_pdf"
    DRM_PROTECTED = "drm_protected"
    PASSWORD_PROTECTED = "password_protected"  # noqa: S105
    DAMAGED = "damaged"


class InspectionError(Exception):
    """Root of the inspection errors."""


class FileRefusedError(InspectionError):
    """The file is not a book the library takes."""

    def __init__(self, refusal: Refusal) -> None:
        super().__init__(refusal.value)
        self.refusal = refusal


class InspectorUnavailableError(InspectionError):
    """The sandbox did not run, so the file has no verdict."""


class InspectorPort(Protocol):
    """Parses one untrusted file in a sandbox and names its format."""

    def inspect(self, source: Path) -> BookFormat:
        """Return the format, or raise `FileRefusedError`."""
        ...


def read_verdict(word: str) -> BookFormat:
    """Turn the sandbox output into a format. Raise on a refusal or an unknown word."""
    raise NotImplementedError
