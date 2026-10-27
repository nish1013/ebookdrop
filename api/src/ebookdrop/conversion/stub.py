"""A converter stub until the sandboxed converter exists."""

from pathlib import Path

from ebookdrop.conversion.port import Conversion


class StubConverter:
    """Keeps the bytes as they are. A `%PDF-` header gives a PDF, else an EPUB."""

    def convert(self, source: Path, work_dir: Path) -> Conversion:
        raise NotImplementedError
