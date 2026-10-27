import uuid

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
