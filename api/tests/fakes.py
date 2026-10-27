from pathlib import Path

from ebookdrop.conversion.port import BookFormat
from ebookdrop.inspection.port import read_verdict
from ebookdrop.inspection.sandbox_check import check


class InProcessInspector:
    """Runs the sandbox check in the test process. Test files only."""

    def __init__(self) -> None:
        self.calls = 0

    def inspect(self, source: Path) -> BookFormat:
        self.calls += 1
        return read_verdict(check(source.read_bytes()))
