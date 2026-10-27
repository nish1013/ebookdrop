import subprocess
from pathlib import Path

from ebookdrop.conversion.port import BookFormat
from ebookdrop.inspection.port import read_verdict
from ebookdrop.inspection.sandbox_check import check

_STARTS = {"create", "start", "run"}
_RUNS = {"attach", "run"}


class InProcessInspector:
    """Runs the sandbox check in the test process. Test files only."""

    def __init__(self) -> None:
        self.calls = 0

    def inspect(self, source: Path) -> BookFormat:
        self.calls += 1
        return read_verdict(check(source.read_bytes()))


class FakeDocker:
    """Answers the docker client commands with no daemon. Test files only."""

    def __init__(
        self,
        *,
        slow_start: bool = False,
        slow_run: bool = False,
        remove: str = "ok",
        verdict: bytes = b"epub\n",
    ) -> None:
        self.slow_start = slow_start
        self.slow_run = slow_run
        self.remove = remove
        self.verdict = verdict
        self.verbs: list[str] = []

    def __call__(
        self, args: list[str], *, timeout: float | None = None, **_: object
    ) -> subprocess.CompletedProcess[bytes]:
        verb = args[1]
        self.verbs.append(verb)
        if verb == "rm":
            if self.remove == "fails":
                raise OSError("docker client lost")
            if self.remove == "hangs":
                _hang(args, timeout)
            return subprocess.CompletedProcess(args, 0, b"", b"")
        if self.slow_start and verb in _STARTS:
            _hang(args, timeout)
        if self.slow_run and verb in _RUNS:
            _hang(args, timeout)
        out = self.verdict if verb in _RUNS else b""
        return subprocess.CompletedProcess(args, 0, out, b"")


def _hang(args: list[str], timeout: float | None) -> None:
    if timeout is None:
        raise AssertionError(f"docker {args[1]} with no time-out never returns")
    raise subprocess.TimeoutExpired(args, timeout)
