import subprocess
import zipfile
from pathlib import Path

import pytest

from ebookdrop.conversion.docker import DockerConverter, convert_command
from ebookdrop.conversion.port import (
    BookFormat,
    ConversionFailedError,
    ConverterPort,
    ConverterUnavailableError,
    Failure,
    SandboxEscapeError,
)
from ebookdrop.conversion.stub import StubConverter
from tests.samples import EPUB_MIMETYPE, PNG_MAGIC, cut, epub, pdf

# The hostile converter with the title "hang" never ends, so any limit is passed.
HANG_SECONDS = 3.0


@pytest.fixture(params=["stub", "docker"])
def converter(request: pytest.FixtureRequest) -> ConverterPort:
    if request.param == "stub":
        return StubConverter()
    return DockerConverter(request.getfixturevalue("image"))


@pytest.fixture
def docker_converter(image: str) -> DockerConverter:
    return DockerConverter(image)


def written(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / "in" / name
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(data)
    return path


def work(tmp_path: Path) -> Path:
    path = tmp_path / "work"
    path.mkdir()
    return path


def test_converter_gives_an_epub_under_the_work_dir(
    converter: ConverterPort, tmp_path: Path
) -> None:
    work_dir = work(tmp_path)

    conversion = converter.convert(written(tmp_path, "dune.epub", epub()), work_dir)

    assert conversion.format == BookFormat.EPUB
    assert conversion.book.parent == work_dir
    with zipfile.ZipFile(conversion.book) as book:
        assert book.read("mimetype") == EPUB_MIMETYPE


def test_converter_keeps_a_pdf_as_it_is(
    converter: ConverterPort, tmp_path: Path
) -> None:
    work_dir = work(tmp_path)
    atlas = pdf()

    conversion = converter.convert(written(tmp_path, "atlas.pdf", atlas), work_dir)

    assert conversion.format == BookFormat.PDF
    assert conversion.book.parent == work_dir
    assert conversion.book.read_bytes() == atlas


def test_converter_gives_no_details_for_a_book_without_them(
    converter: ConverterPort, tmp_path: Path
) -> None:
    conversion = converter.convert(written(tmp_path, "scan.pdf", pdf()), work(tmp_path))

    assert (conversion.title, conversion.author, conversion.cover) == (None, None, None)


def test_sandbox_converter_reads_the_title_author_and_a_png_cover(
    docker_converter: DockerConverter, tmp_path: Path
) -> None:
    dune = epub(title="Dune", author="Frank Herbert", cover=True)
    work_dir = work(tmp_path)

    conversion = docker_converter.convert(
        written(tmp_path, "dune.epub", dune), work_dir
    )

    assert (conversion.title, conversion.author) == ("Dune", "Frank Herbert")
    assert conversion.cover is not None
    assert conversion.cover.parent == work_dir
    assert conversion.cover.read_bytes().startswith(PNG_MAGIC)


def test_sandbox_converter_reads_the_title_of_a_pdf(
    docker_converter: DockerConverter, tmp_path: Path
) -> None:
    atlas = pdf(title="World Atlas")

    conversion = docker_converter.convert(
        written(tmp_path, "atlas.pdf", atlas), work(tmp_path)
    )

    assert (conversion.title, conversion.cover) == ("World Atlas", None)


@pytest.mark.parametrize(
    ("name", "data", "failure"),
    [
        ("broken.epub", cut(epub(padding=64 * 1024), 0.6), Failure.MALFORMED),
        ("blank.epub", epub(blank=True), Failure.UNREADABLE),
        ("notes.txt", b"plain text, not a book", Failure.MALFORMED),
    ],
    ids=["cut_zip", "blank_first_page", "not_a_book"],
)
def test_sandbox_converter_fails_a_bad_book_with_its_reason(
    docker_converter: DockerConverter,
    tmp_path: Path,
    name: str,
    data: bytes,
    failure: Failure,
) -> None:
    with pytest.raises(ConversionFailedError) as failed:
        docker_converter.convert(written(tmp_path, name, data), work(tmp_path))

    assert failed.value.failure == failure


def test_sandbox_converter_past_its_time_limit_fails_and_removes_the_container(
    evil_image: str, tmp_path: Path
) -> None:
    converter = DockerConverter(evil_image, timeout=HANG_SECONDS)
    hang = epub(title="hang")

    with pytest.raises(ConversionFailedError) as failed:
        converter.convert(written(tmp_path, "slow.epub", hang), work(tmp_path))

    assert failed.value.failure == Failure.TIMED_OUT
    left = subprocess.run(
        ["docker", "ps", "-aq", "--filter", "name=ebookdrop-convert-"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert left.stdout.strip() == ""


def test_sandbox_converter_blocks_a_book_that_opens_a_socket(
    evil_image: str, tmp_path: Path
) -> None:
    converter = DockerConverter(evil_image)

    with pytest.raises(SandboxEscapeError) as failed:
        converter.convert(written(tmp_path, "evil.epub", epub()), work(tmp_path))

    assert failed.value.failure == Failure.CRASHED


PROBE = """
import pathlib, socket
print(pathlib.Path('/sys/fs/cgroup/memory.max').read_text().strip(), flush=True)
print(pathlib.Path('/sys/fs/cgroup/pids.max').read_text().strip(), flush=True)
try:
    pathlib.Path('/probe').write_text('x')
    print('root writable', flush=True)
except OSError:
    print('root read-only', flush=True)
socket.socket(socket.AF_UNIX).close()
print('unix socket open', flush=True)
socket.create_connection(('1.1.1.1', 53), timeout=2)
print('network open', flush=True)
"""
SIGSYS_EXIT = 128 + 31


def test_convert_sandbox_has_its_limits_and_kills_a_network_socket(
    image: str,
) -> None:
    command = convert_command("ebookdrop-convert-probe", image, verb="run")
    at = command.index(image)
    probe = [*command[:at], "--entrypoint", "python", image, "-c", PROBE]

    done = subprocess.run(
        probe, input="", capture_output=True, text=True, timeout=60, check=False
    )

    assert done.stdout.splitlines() == [
        str(512 * 1024 * 1024),
        "64",
        "root read-only",
        "unix socket open",
    ]
    assert done.returncode == SIGSYS_EXIT
    assert command[command.index("--network") + 1] == "none"


def test_docker_converter_with_no_image_is_unavailable_not_a_failure(
    tmp_path: Path,
) -> None:
    converter = DockerConverter("ebookdrop-sandbox:absent")

    with pytest.raises(ConverterUnavailableError):
        converter.convert(written(tmp_path, "dune.epub", epub()), work(tmp_path))
