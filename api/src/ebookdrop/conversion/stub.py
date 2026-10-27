"""A converter stub until the sandboxed converter exists."""

import shutil
from pathlib import Path

from ebookdrop.conversion.port import BookFormat, Conversion

_PDF_HEADER = b"%PDF-"


class StubConverter:
    """Keeps the bytes as they are. A `%PDF-` header gives a PDF, else an EPUB."""

    def convert(self, source: Path, work_dir: Path) -> Conversion:
        """Copy `source` to `work_dir` as the book. Give no details and no cover."""
        with source.open("rb") as file:
            pdf = file.read(len(_PDF_HEADER)) == _PDF_HEADER
        book_format = BookFormat.PDF if pdf else BookFormat.EPUB
        book = work_dir / f"book.{book_format}"
        shutil.copyfile(source, book)
        return Conversion(book_format, book, None, None, None)
