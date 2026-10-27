import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from ebookdrop.storage import LocalDiskStorage
from tests.api.conftest import (
    CHUNK,
    PART_TAIL,
    chunks,
    count,
    events,
    fill_library,
    intake_events,
    library_bytes,
    part_head,
    post_raw,
    refuse,
    sign_in,
    sign_up,
    upload,
)
from tests.samples import DRM_ALGORITHM, cut, epub, pdf

DUNE = epub(padding=2 * 1024 * 1024)


def test_s4_ac1_upload_shows_the_file_as_processing(
    client: TestClient, engine: Engine, signed_in_ana: str
) -> None:
    book = upload(client, "dune.epub", DUNE)

    assert book["title"] == "dune.epub"
    assert book["status"] == "processing"
    assert client.get("/api/books").json() == [book]
    assert events(engine, book["id"]) == ["upload_received", "conversion_queued"]


def test_s4_ac7_signed_out_upload_gets_401_and_no_event(
    client: TestClient, engine: Engine, storage: LocalDiskStorage
) -> None:
    response = client.post("/api/books", files={"file": ("dune.epub", DUNE)})

    assert response.status_code == 401
    assert response.json() == {"code": "signed_out"}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM books")).scalar() == 0
        assert (
            connection.execute(text("SELECT count(*) FROM book_events")).scalar() == 0
        )


MIB = 1024 * 1024
QUOTA = 1024 * MIB


def parallel_uploads(
    client: TestClient, email: str, files: list[tuple[str, bytes]]
) -> list[tuple[int, Any]]:
    """Upload each file from its own client, all released by one barrier."""
    start = threading.Barrier(len(files))
    answers: list[tuple[int, Any]] = []

    def send(name: str, content: bytes) -> None:
        with TestClient(client.app, base_url="https://testserver") as own:
            assert sign_in(own, email) == 204
            start.wait()
            answers.append(refuse(own, name, content))

    threads = [threading.Thread(target=send, args=file) for file in files]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return answers


def test_s4_ac2_zip_without_epub_mimetype_is_not_epub_or_pdf(
    client: TestClient, engine: Engine, signed_in_ana: str
) -> None:
    answer = refuse(client, "notes.epub", epub(mimetype=False))

    assert answer == (422, {"code": "not_epub_or_pdf"})
    assert count(engine, "books") == 0
    assert intake_events(engine) == [("upload_rejected", "not_epub_or_pdf")]


def test_s4_ac3_larger_content_length_is_rejected_before_any_body_byte(
    client: TestClient, engine: Engine, signed_in_ana: str
) -> None:
    head = part_head("atlas.pdf")
    declared = len(head) + 51 * MIB + len(PART_TAIL)

    answer = post_raw(
        client, chunks(head + bytes(51 * MIB) + PART_TAIL), content_length=declared
    )

    assert (answer.status, answer.body) == (413, {"code": "too_large"})
    assert answer.sent == 0
    assert count(engine, "books") == 0
    assert intake_events(engine) == [("upload_rejected", "too_large")]


def test_s4_ac14_stream_with_no_length_stops_at_50_mib_and_one_byte(
    client: TestClient, engine: Engine, storage: LocalDiskStorage, signed_in_ana: str
) -> None:
    head = part_head("huge.pdf")

    def four_gib() -> Iterator[bytes]:
        yield head
        for _ in range(4 * 1024 * MIB // CHUNK):
            yield bytes(CHUNK)

    answer = post_raw(client, four_gib())

    assert (answer.status, answer.body) == (413, {"code": "too_large"})
    assert 50 * MIB < answer.sent - len(head) <= 50 * MIB + CHUNK
    assert count(engine, "books") == 0
    assert intake_events(engine) == [("upload_rejected", "too_large")]


def test_s4_ac4_epub_with_drm_encryption_is_drm_protected(
    client: TestClient, engine: Engine, signed_in_ana: str
) -> None:
    answer = refuse(client, "store.epub", epub(encryption=DRM_ALGORITHM))

    assert answer == (422, {"code": "drm_protected"})
    assert count(engine, "books") == 0


def test_s4_ac11_pdf_that_needs_a_password_is_password_protected(
    client: TestClient, engine: Engine, signed_in_ana: str
) -> None:
    answer = refuse(client, "bank.pdf", pdf(user="secret", owner="owner"))

    assert answer == (422, {"code": "password_protected"})
    assert count(engine, "books") == 0


def test_s4_ac12_pdf_that_opens_with_no_password_and_blocks_print_is_received(
    client: TestClient, engine: Engine, signed_in_ana: str
) -> None:
    book = upload(client, "tax-guide.pdf", pdf(owner="owner", allow_print=False))

    assert book["status"] == "processing"
    assert events(engine, book["id"])[0] == "upload_received"


def test_s4_ac13_zip_cut_at_60_percent_is_damaged(
    client: TestClient, engine: Engine, signed_in_ana: str
) -> None:
    answer = refuse(client, "cut.epub", cut(epub(padding=64 * 1024), 0.6))

    assert answer == (422, {"code": "damaged"})
    assert count(engine, "books") == 0


def test_s4_ac5_upload_stopped_at_1_mb_of_2_mb_leaves_no_row(
    client: TestClient,
    engine: Engine,
    storage: LocalDiskStorage,
    tmp_path: Path,
    signed_in_ana: str,
) -> None:
    body = part_head("dune.epub") + DUNE + PART_TAIL

    post_raw(client, chunks(body[: 1 * MIB]), disconnect=True)

    assert count(engine, "books") == 0
    assert count(engine, "book_events") == 0
    assert intake_events(engine) == [("upload_abandoned", None)]
    assert not (tmp_path / "storage").exists()


def test_s4_ac6_same_bytes_again_are_rejected_with_a_link_to_the_book(
    client: TestClient, engine: Engine, signed_in_ana: str
) -> None:
    first = upload(client, "dune.epub", DUNE)

    answer = refuse(client, "dune-copy.epub", DUNE)

    assert answer == (
        409,
        {"code": "duplicate_upload", "book_id": first["id"], "title": "dune.epub"},
    )
    assert [b["id"] for b in client.get("/api/books").json()] == [first["id"]]
    assert intake_events(engine) == [("duplicate_upload_detected", None)]
    assert library_bytes(engine, signed_in_ana) == (len(DUNE), len(DUNE))


def test_s4_ac6_two_uploads_of_the_same_bytes_at_once_make_one_book(
    client: TestClient, engine: Engine, signed_in_ana: str
) -> None:
    answers = parallel_uploads(
        client, signed_in_ana, [("dune.epub", DUNE), ("dune-copy.epub", DUNE)]
    )

    assert sorted(status for status, _ in answers) == [201, 409]
    assert count(engine, "books") == 1
    assert library_bytes(engine, signed_in_ana) == (len(DUNE), len(DUNE))


def test_s4_ac8_another_reader_with_the_same_bytes_gets_an_own_book(
    client: TestClient, engine: Engine, signed_in_ana: str
) -> None:
    upload(client, "dune.epub", DUNE)
    assert sign_up(client, "ben@example.com") == 201
    assert sign_in(client, "ben@example.com") == 204

    book = upload(client, "dune.epub", DUNE)

    assert [b["id"] for b in client.get("/api/books").json()] == [book["id"]]
    assert count(engine, "books") == 2


def test_s4_ac9_upload_past_1_gib_is_over_quota(
    client: TestClient, engine: Engine, storage: LocalDiskStorage, signed_in_ana: str
) -> None:
    stored, atlas = 1010 * MIB, epub(padding=20 * MIB)
    assert stored + len(atlas) > QUOTA
    fill_library(engine, signed_in_ana, stored, 50 * MIB)

    answer = refuse(client, "atlas.epub", atlas)

    assert answer == (422, {"code": "over_quota"})
    assert library_bytes(engine, signed_in_ana) == (stored, stored)
    assert intake_events(engine) == [("upload_rejected", "over_quota")]


def test_s4_ac10_two_uploads_at_once_past_the_quota_make_one_book(
    client: TestClient, engine: Engine, signed_in_ana: str
) -> None:
    stored = 980 * MIB
    first, second = epub(padding=30 * MIB, seed=1), epub(padding=30 * MIB, seed=2)
    assert stored + len(first) <= QUOTA
    assert stored + len(second) <= QUOTA
    assert stored + len(first) + len(second) > QUOTA
    fill_library(engine, signed_in_ana, stored, 49 * MIB)

    answers = parallel_uploads(
        client, signed_in_ana, [("one.epub", first), ("two.epub", second)]
    )

    assert sorted(answers, key=lambda a: a[0])[1] == (422, {"code": "over_quota"})
    assert sorted(status for status, _ in answers) == [201, 422]
    used, total = library_bytes(engine, signed_in_ana)
    assert used == total <= QUOTA
