from datetime import timedelta
from pathlib import Path

import pytest

from ebookdrop.conversion.port import BookFormat
from ebookdrop.conversion.stub import StubConverter
from ebookdrop.library.domain import (
    FileName,
    InvalidFileNameError,
    removal_retry_after,
)
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


def test_a_removal_waits_10_s_then_doubles_up_to_1_h_after_any_failure_count() -> None:
    waits = [removal_retry_after(n) for n in (1, 2, 3, 10, 50, 10_000)]

    assert waits == [
        timedelta(seconds=10),
        timedelta(seconds=20),
        timedelta(seconds=40),
        timedelta(hours=1),
        timedelta(hours=1),
        timedelta(hours=1),
    ]
