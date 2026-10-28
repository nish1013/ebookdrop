import hashlib
import io

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ebookdrop.conversion.port import BookFormat
from ebookdrop.inspection.port import (
    FileRefusedError,
    InspectorUnavailableError,
    Refusal,
    read_verdict,
)
from ebookdrop.inspection.sandbox_check import check
from ebookdrop.library.domain import RejectReason, UploadRejectedError
from ebookdrop.library.upload_stream import UploadSink
from tests.samples import DRM_ALGORITHM, FONT_OBFUSCATION, cut, epub, pdf

SMALL_EPUB = epub()


@pytest.mark.parametrize(
    ("data", "verdict"),
    [
        (epub(), "epub"),
        (epub(mimetype=False), "not_epub_or_pdf"),
        (epub(encryption=DRM_ALGORITHM), "drm_protected"),
        (epub(encryption=FONT_OBFUSCATION), "epub"),
        (cut(epub(), 0.6), "damaged"),
        (pdf(), "pdf"),
        (pdf(owner="owner", allow_print=False), "pdf"),
        (pdf(user="secret", owner="owner"), "password_protected"),
        (b"%PDF-1.7 no objects", "damaged"),
        (b"", "not_epub_or_pdf"),
        (b"plain text, no book", "not_epub_or_pdf"),
    ],
    ids=[
        "epub",
        "zip-without-mimetype",
        "drm",
        "font-obfuscation-only",
        "cut-zip",
        "pdf",
        "print-limit-only",
        "password-pdf",
        "broken-pdf",
        "empty",
        "text",
    ],
)
def test_sandbox_check_names_the_format_or_the_refusal(
    data: bytes, verdict: str
) -> None:
    assert check(data) == verdict


def test_read_verdict_maps_words_to_a_format_or_a_refusal() -> None:
    assert read_verdict("epub\n") == BookFormat.EPUB
    assert read_verdict("pdf") == BookFormat.PDF
    with pytest.raises(FileRefusedError) as refused:
        read_verdict("drm_protected")
    assert refused.value.refusal == Refusal.DRM_PROTECTED
    with pytest.raises(InspectorUnavailableError):
        read_verdict("Traceback (most recent call last)")


def test_every_refusal_is_a_reject_reason() -> None:
    assert {r.value for r in Refusal} <= {r.value for r in RejectReason}


@given(st.integers(min_value=0, max_value=len(SMALL_EPUB) - 1))
def test_any_cut_of_an_epub_is_never_accepted(size: int) -> None:
    verdict = check(SMALL_EPUB[:size])

    assert verdict == ("damaged" if size >= 4 else "not_epub_or_pdf")


@given(
    data=st.binary(max_size=300),
    splits=st.lists(st.integers(min_value=0, max_value=300), max_size=8),
    limit=st.integers(min_value=0, max_value=300),
)
def test_sink_keeps_and_hashes_the_bytes_and_never_writes_past_the_limit(
    data: bytes, splits: list[int], limit: int
) -> None:
    cuts = sorted({0, len(data), *(s for s in splits if s <= len(data))})
    target = io.BytesIO()
    sink = UploadSink(target, limit)

    try:
        for start, end in zip(cuts, cuts[1:], strict=False):
            sink.write(data[start:end])
    except UploadRejectedError as rejected:
        assert rejected.reason == RejectReason.TOO_LARGE
        assert len(data) > limit
        assert len(target.getvalue()) <= limit
        return

    assert len(data) <= limit
    assert target.getvalue() == data
    assert sink.size == len(data)
    assert sink.sha256 == hashlib.sha256(data).hexdigest()
