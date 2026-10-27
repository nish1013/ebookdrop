"""The Docker adapter of `ConverterPort`: one locked-down container per job."""

import json
import shutil
import subprocess
import tarfile
import uuid
from pathlib import Path

from ebookdrop.conversion.port import (
    CONVERT_SECONDS,
    BookFormat,
    Conversion,
    ConversionFailedError,
    ConverterUnavailableError,
    Failure,
    SandboxEscapeError,
)
from ebookdrop.conversion.sandbox_convert import (
    CRASH_EXIT,
    ESCAPE_EXIT,
    MALFORMED_EXIT,
    MAX_BYTES,
    UNREADABLE_EXIT,
)
from ebookdrop.sandbox import SANDBOX_IMAGE, Runner, remove, sandbox_command

NAME_PREFIX = "ebookdrop-convert-"
SECCOMP_PROFILE = Path(__file__).with_name("seccomp.json")
# The profile kills a process that opens an IPv4 or IPv6 socket: exit 128 + SIGSYS.
_SIGSYS_EXIT = 159
_ESCAPE_EXITS = {ESCAPE_EXIT, _SIGSYS_EXIT}
_FAILURES = {
    MALFORMED_EXIT: Failure.MALFORMED,
    UNREADABLE_EXIT: Failure.UNREADABLE,
    CRASH_EXIT: Failure.CRASHED,
    137: Failure.CRASHED,
}
# The docker client exits 1 when the daemon is down, 125-127 when it cannot run.
_UNAVAILABLE_EXITS = {1, 125, 126, 127}
_LIMITS = {
    "details.json": 64 * 1024,
    "book.epub": 2 * MAX_BYTES,
    "cover.png": 8 * 1024 * 1024,
}
_MAX_OUTPUT = sum(_LIMITS.values()) + 64 * 1024
_UNPACK_ERRORS = (tarfile.TarError, KeyError, ValueError, TypeError, OSError)


def convert_command(name: str, image: str) -> list[str]:
    """The `docker run` line of one convert container."""
    options = [
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=256m",  # noqa: S108
        "--security-opt",
        f"seccomp={SECCOMP_PROFILE}",
        "--env",
        "HOME=/tmp",
        "--env",
        "QT_QPA_PLATFORM=offscreen",
        "--entrypoint",
        "python",
    ]
    return [
        *sandbox_command(name, image, options),
        "-I",
        "-B",
        "/sandbox/sandbox_convert.py",
    ]


class DockerConverter:
    """Runs `sandbox_convert` in a container with no network and tight limits."""

    def __init__(
        self,
        image: str = SANDBOX_IMAGE,
        timeout: float = CONVERT_SECONDS,
        run: Runner = subprocess.run,
    ) -> None:
        self._image = image
        self._timeout = timeout
        self._run = run

    def convert(self, source: Path, work_dir: Path) -> Conversion:
        """Pipe `source` to a new container and unpack its output.

        The output passes through a tar file in `work_dir`, and only the expected
        names leave it, each under its size limit.
        """
        name = f"{NAME_PREFIX}{uuid.uuid4().hex}"
        output = work_dir / "sandbox.tar"
        try:
            with source.open("rb") as stdin, output.open("wb") as stdout:
                done = self._run(
                    convert_command(name, self._image),
                    stdin=stdin,
                    stdout=stdout,
                    stderr=subprocess.DEVNULL,
                    timeout=self._timeout,
                    check=False,
                )
        except subprocess.TimeoutExpired:
            remove(name, self._run)
            raise ConversionFailedError(Failure.TIMED_OUT) from None
        except OSError as err:
            raise ConverterUnavailableError("docker did not start") from err
        _check_exit(done.returncode)
        try:
            return _unpack(output, source, work_dir)
        except _UNPACK_ERRORS as err:
            raise ConversionFailedError(Failure.CRASHED) from err
        finally:
            output.unlink(missing_ok=True)


def _check_exit(code: int) -> None:
    if code == 0:
        return
    if code in _ESCAPE_EXITS:
        raise SandboxEscapeError
    if code in _UNAVAILABLE_EXITS:
        raise ConverterUnavailableError(f"docker exit {code}")
    raise ConversionFailedError(_FAILURES.get(code, Failure.CRASHED))


def _unpack(output: Path, source: Path, work_dir: Path) -> Conversion:
    if output.stat().st_size > _MAX_OUTPUT:
        raise ValueError("output too large")
    with tarfile.open(output, "r:") as tar:
        files = {m.name: _read(tar, m) for m in tar.getmembers() if m.name in _LIMITS}
    details = json.loads(files["details.json"])
    book_format = BookFormat(details["format"])
    book = work_dir / f"book.{book_format}"
    if book_format == BookFormat.PDF:
        shutil.copyfile(source, book)
    else:
        book.write_bytes(files["book.epub"])
    cover = None
    if "cover.png" in files:
        cover = work_dir / "cover.png"
        cover.write_bytes(files["cover.png"])
    return Conversion(
        book_format,
        book,
        _optional_text(details.get("title")),
        _optional_text(details.get("author")),
        cover,
    )


def _read(tar: tarfile.TarFile, member: tarfile.TarInfo) -> bytes:
    limit = _LIMITS[member.name]
    extracted = tar.extractfile(member) if member.isfile() else None
    if extracted is None or member.size > limit:
        raise ValueError(member.name)
    return extracted.read(limit + 1)


def _optional_text(value: object) -> str | None:
    if value is None or isinstance(value, str):
        return value
    raise TypeError("detail is not text")
