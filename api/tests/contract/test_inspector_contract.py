import io
import subprocess
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from ebookdrop.conversion.port import BookFormat
from ebookdrop.inspection.docker import DockerInspector, sandbox_command
from ebookdrop.inspection.port import FileRefusedError, InspectorPort, Refusal
from tests.fakes import InProcessInspector
from tests.samples import DRM_ALGORITHM, EPUB_MIMETYPE, cut, epub, pdf

API = Path(__file__).resolve().parents[2]
TEST_IMAGE = "ebookdrop-inspect:test"
ACCEPTED = [
    ("dune.epub", epub(), BookFormat.EPUB),
    ("tax-guide.pdf", pdf(owner="owner", allow_print=False), BookFormat.PDF),
]
REFUSED = [
    ("notes.epub", epub(mimetype=False), Refusal.NOT_EPUB_OR_PDF),
    ("store.epub", epub(encryption=DRM_ALGORITHM), Refusal.DRM_PROTECTED),
    ("bank.pdf", pdf(user="secret", owner="owner"), Refusal.PASSWORD_PROTECTED),
    ("cut.epub", cut(epub(padding=64 * 1024), 0.6), Refusal.DAMAGED),
]


@pytest.fixture(scope="session")
def image() -> str:
    subprocess.run(
        ["docker", "build", "-q", "-t", TEST_IMAGE, "-f", "sandbox/Dockerfile", "."],
        cwd=API,
        check=True,
        capture_output=True,
    )
    return TEST_IMAGE


@pytest.fixture(params=["in_process", "docker"])
def inspector(request: pytest.FixtureRequest) -> InspectorPort:
    if request.param == "in_process":
        return InProcessInspector()
    return DockerInspector(request.getfixturevalue("image"))


def written(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


@pytest.mark.parametrize(
    ("name", "data", "found"), ACCEPTED, ids=[a[0] for a in ACCEPTED]
)
def test_inspector_names_the_format_of_a_good_file(
    inspector: InspectorPort, tmp_path: Path, name: str, data: bytes, found: BookFormat
) -> None:
    assert inspector.inspect(written(tmp_path, name, data)) == found


@pytest.mark.parametrize(
    ("name", "data", "refusal"), REFUSED, ids=[r[0] for r in REFUSED]
)
def test_inspector_refuses_a_bad_file_with_its_reason(
    inspector: InspectorPort, tmp_path: Path, name: str, data: bytes, refusal: Refusal
) -> None:
    with pytest.raises(FileRefusedError) as refused:
        inspector.inspect(written(tmp_path, name, data))

    assert refused.value.refusal == refusal


PROBE = """
import pathlib, socket
print(pathlib.Path('/sys/fs/cgroup/memory.max').read_text().strip())
print(pathlib.Path('/sys/fs/cgroup/pids.max').read_text().strip())
try:
    pathlib.Path('/probe').write_text('x')
    print('root writable')
except OSError:
    print('root read-only')
try:
    socket.create_connection(('1.1.1.1', 53), timeout=2)
    print('network open')
except OSError:
    print('network closed')
"""


def test_sandbox_has_no_network_a_read_only_root_and_its_limits(image: str) -> None:
    command = sandbox_command("ebookdrop-inspect-probe", image)
    at = command.index(image)
    probe = [*command[:at], "--entrypoint", "python", image, "-c", PROBE]

    done = subprocess.run(
        probe, input="", capture_output=True, text=True, timeout=60, check=True
    )

    assert done.stdout.splitlines() == [
        str(512 * 1024 * 1024),
        "64",
        "root read-only",
        "network closed",
    ]


def _deflated(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name)
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


@pytest.fixture
def zip_bomb(tmp_path: Path) -> Iterator[Path]:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as book:
        book.writestr("mimetype", EPUB_MIMETYPE, zipfile.ZIP_STORED)
        with book.open(_deflated("OEBPS/bomb.xhtml"), "w", force_zip64=True) as bomb:
            zeros = bytes(1024 * 1024)
            for _ in range(2048):
                bomb.write(zeros)
    path = tmp_path / "bomb.epub"
    path.write_bytes(buffer.getvalue())
    yield path


def test_inspect_past_its_time_limit_refuses_and_removes_the_container(
    image: str, zip_bomb: Path
) -> None:
    inspector = DockerInspector(image, timeout=1.0)

    with pytest.raises(FileRefusedError) as refused:
        inspector.inspect(zip_bomb)

    assert refused.value.refusal == Refusal.DAMAGED
    left = subprocess.run(
        ["docker", "ps", "-aq", "--filter", "name=ebookdrop-inspect-"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert left.stdout.strip() == ""
