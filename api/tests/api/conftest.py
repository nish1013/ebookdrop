import asyncio
import hashlib
import json
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from ebookdrop.app import conversion_jobs
from ebookdrop.conversion.port import ConverterPort
from ebookdrop.conversion.stub import StubConverter
from ebookdrop.library.conversion_jobs import ConversionJobs
from ebookdrop.storage import LocalDiskStorage
from tests.conftest import FakeClock

PASSWORD = "correct horse battery"


def sign_up(client: TestClient, email: str, password: str = PASSWORD) -> int:
    response = client.post("/api/accounts", json={"email": email, "password": password})
    return response.status_code


def sign_in(client: TestClient, email: str, password: str = PASSWORD) -> int:
    response = client.post("/api/sessions", json={"email": email, "password": password})
    return response.status_code


@pytest.fixture
def ana(client: TestClient) -> str:
    assert sign_up(client, "ana@example.com") == 201
    return "ana@example.com"


def upload(client: TestClient, name: str, content: bytes) -> dict[str, object]:
    response = client.post("/api/books", files={"file": (name, content)})
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


def refuse(client: TestClient, name: str, content: bytes) -> tuple[int, Any]:
    response = client.post("/api/books", files={"file": (name, content)})
    return response.status_code, response.json()


BOUNDARY = "ebookdrop-test-boundary"
CHUNK = 64 * 1024


def part_head(name: str) -> bytes:
    return (
        f"--{BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode()


PART_TAIL = f"\r\n--{BOUNDARY}--\r\n".encode()


def chunks(data: bytes) -> Iterator[bytes]:
    for start in range(0, len(data), CHUNK):
        yield data[start : start + CHUNK]


@dataclass
class RawAnswer:
    status: int
    body: Any
    sent: int


def post_raw(
    client: TestClient,
    body: Iterable[bytes],
    *,
    content_length: int | None = None,
    disconnect: bool = False,
) -> RawAnswer:
    """POST /api/books as raw ASGI messages, counting the body bytes the app pulls."""
    headers = [
        (b"content-type", f"multipart/form-data; boundary={BOUNDARY}".encode()),
        (b"cookie", f"session={client.cookies['session']}".encode()),
    ]
    if content_length is not None:
        headers.append((b"content-length", str(content_length).encode()))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": "/api/books",
        "raw_path": b"/api/books",
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("testclient", 50000),
        "server": ("testserver", 443),
    }
    source = iter(body)
    answer = RawAnswer(0, None, 0)
    ended = False
    sent_body = bytearray()

    async def receive() -> dict[str, object]:
        nonlocal ended
        chunk = None if ended else next(source, None)
        if chunk is None:
            ended = True
            if disconnect:
                return {"type": "http.disconnect"}
            return {"type": "http.request", "body": b"", "more_body": False}
        answer.sent += len(chunk)
        return {"type": "http.request", "body": chunk, "more_body": True}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            answer.status = message["status"]
        elif message["type"] == "http.response.body":
            sent_body.extend(message.get("body", b""))

    asyncio.run(client.app(scope, receive, send))  # type: ignore[arg-type]
    answer.body = json.loads(sent_body) if sent_body else None
    return answer


def reader_id(engine: Engine, email: str) -> uuid.UUID:
    query = text("SELECT id FROM accounts WHERE email = :email")
    with engine.connect() as connection:
        found: uuid.UUID = connection.execute(query, {"email": email}).scalar_one()
    return found


def fill_library(engine: Engine, email: str, total: int, max_book: int) -> None:
    """Give the reader stored books of `total` bytes, each `max_book` or smaller."""
    reader = reader_id(engine, email)
    sizes = [max_book] * (total // max_book) + (
        [total % max_book] if total % max_book else []
    )
    rows = [
        {
            "id": uuid.uuid4(),
            "reader": reader,
            "sha": hashlib.sha256(f"{email}-{n}".encode()).hexdigest(),
            "size": size,
        }
        for n, size in enumerate(sizes)
    ]
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO books (id, reader_id, file_name, title, status,"
                " received_at, sha256, size) VALUES (:id, :reader, 'old.pdf',"
                " 'old.pdf', 'ready', now(), :sha, :size)"
            ),
            rows,
        )
        connection.execute(
            text(
                "INSERT INTO libraries (reader_id, bytes_used) VALUES (:r, :t)"
                " ON CONFLICT (reader_id) DO UPDATE SET bytes_used = :t"
            ),
            {"r": reader, "t": total},
        )


def library_bytes(engine: Engine, email: str) -> tuple[int, int]:
    """Return `bytes_used` and the sum of the reader's book sizes."""
    reader = reader_id(engine, email)
    with engine.connect() as connection:
        used = connection.execute(
            text("SELECT bytes_used FROM libraries WHERE reader_id = :r"),
            {"r": reader},
        ).scalar()
        total = connection.execute(
            text("SELECT coalesce(sum(size), 0) FROM books WHERE reader_id = :r"),
            {"r": reader},
        ).scalar()
    return int(used or 0), int(total or 0)


_COUNTS = {
    table: text(f"SELECT count(*) FROM {table}")  # noqa: S608
    for table in ("books", "book_events", "libraries")
}


def count(engine: Engine, table: str) -> int:
    with engine.connect() as connection:
        return int(connection.execute(_COUNTS[table]).scalar() or 0)


def intake_events(engine: Engine) -> list[tuple[str, str | None]]:
    query = text("SELECT name, reason FROM intake_events ORDER BY id")
    with engine.connect() as connection:
        return [(r.name, r.reason) for r in connection.execute(query)]


def events(engine: Engine, book_id: object) -> list[str]:
    query = text("SELECT name FROM book_events WHERE book_id = :id ORDER BY id")
    with engine.connect() as connection:
        return list(
            connection.execute(query, {"id": uuid.UUID(str(book_id))}).scalars()
        )


@pytest.fixture
def signed_in_ana(client: TestClient, ana: str) -> str:
    assert sign_in(client, ana) == 204
    return ana


@pytest.fixture
def converter() -> ConverterPort:
    return StubConverter()


@pytest.fixture
def jobs(
    engine: Engine,
    clock: FakeClock,
    storage: LocalDiskStorage,
    converter: ConverterPort,
) -> ConversionJobs:
    return conversion_jobs(engine, clock, storage, converter)
