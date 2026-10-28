from pathlib import Path

import pytest

from ebookdrop.conversion.port import BookFormat
from ebookdrop.conversion.stub import StubConverter
from ebookdrop.library.domain import FileName, InvalidFileNameError
from ebookdrop.storage import InvalidKeyError, LocalDiskStorage


@pytest.mark.parametrize(
    ("raw", "kept"),
    [
        ("dune.epub", "dune.epub"),
        ("  dune.epub ", "dune.epub"),
        ("../../etc/dune.epub", "dune.epub"),
        ("C:\\books\\dune.epub", "dune.epub"),
    ],
)
def test_file_name_keeps_the_last_part_without_spaces(raw: str, kept: str) -> None:
    assert FileName.parse(raw).value == kept


@pytest.mark.parametrize("raw", [None, "", "   ", "books/", "a" * 256])
def test_file_name_refuses_an_empty_or_long_name(raw: str | None) -> None:
    with pytest.raises(InvalidFileNameError):
        FileName.parse(raw)


@pytest.mark.parametrize("key", ["../outside", "/etc/passwd", "books/../../x", ""])
def test_storage_refuses_a_key_outside_its_root(tmp_path: Path, key: str) -> None:
    with pytest.raises(InvalidKeyError):
        LocalDiskStorage(tmp_path).open(key)


@pytest.mark.parametrize(
    ("head", "found"), [(b"%PDF-1.7", BookFormat.PDF), (b"PK\x03\x04", BookFormat.EPUB)]
)
def test_stub_converter_keeps_the_bytes_and_names_the_format(
    tmp_path: Path, head: bytes, found: BookFormat
) -> None:
    source = tmp_path / "original"
    source.write_bytes(head + b"rest")

    conversion = StubConverter().convert(source, tmp_path)

    assert conversion.format == found
    assert conversion.book.read_bytes() == head + b"rest"
    assert (conversion.title, conversion.author, conversion.cover) == (None, None, None)
