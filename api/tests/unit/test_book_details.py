import pytest
from hypothesis import given
from hypothesis import strategies as st

from ebookdrop.library.domain import (
    MAX_DETAIL_LENGTH,
    UNKNOWN_AUTHOR,
    BookDetails,
    FileName,
)

SCAN = FileName("scan.pdf")


@pytest.mark.parametrize(
    ("title", "author", "file_name", "shown"),
    [
        ("Dune", "Frank Herbert", "dune.epub", ("Dune", "Frank Herbert")),
        (None, None, "scan.pdf", ("scan", UNKNOWN_AUTHOR)),
        ("   ", "\n\t", "scan.pdf", ("scan", UNKNOWN_AUTHOR)),
        (
            "  Dune \n Messiah ",
            " Frank\tHerbert ",
            "x.epub",
            ("Dune Messiah", "Frank Herbert"),
        ),
        ("Du\x00ne\x1b", "Frank​ Herbert", "x.epub", ("Dune", "Frank Herbert")),
        (None, None, "the.long.road.epub", ("the.long.road", UNKNOWN_AUTHOR)),
        (None, None, ".epub", (".epub", UNKNOWN_AUTHOR)),
        (None, None, "notes", ("notes", UNKNOWN_AUTHOR)),
    ],
)
def test_book_details_clean_each_value_and_fill_a_missing_one(
    title: str | None,
    author: str | None,
    file_name: str,
    shown: tuple[str, str],
) -> None:
    details = BookDetails.extracted(title, author, FileName(file_name))

    assert (details.title, details.author) == shown


def test_book_details_cut_a_long_title() -> None:
    details = BookDetails.extracted("a" * 10_000, None, SCAN)

    assert details.title == "a" * MAX_DETAIL_LENGTH


@given(st.none() | st.text(), st.none() | st.text(), st.text(min_size=1, max_size=255))
def test_book_details_are_never_empty_long_or_unprintable(
    title: str | None, author: str | None, raw_name: str
) -> None:
    details = BookDetails.extracted(title, author, FileName(raw_name.strip() or "x"))

    for value in (details.title, details.author):
        assert value
        assert value == value.strip()
        assert len(value) <= MAX_DETAIL_LENGTH
        assert value.isprintable()
