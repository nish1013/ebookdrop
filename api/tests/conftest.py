from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, MetaData, create_engine, text
from testcontainers.community.postgres import PostgresContainer

from ebookdrop.app import create_app
from ebookdrop.storage import LocalDiskStorage
from tests.fakes import InProcessInspector


class FakeClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 10, 27, 9, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, by: timedelta) -> None:
        self.current += by


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as postgres:
        url = postgres.get_connection_url()
        config = Config("alembic.ini")
        config.attributes["url"] = url
        command.upgrade(config, "head")
        yield url


@pytest.fixture
def engine(database_url: str) -> Iterator[Engine]:
    engine = create_engine(database_url)
    tables = MetaData()
    tables.reflect(engine)
    names = [name for name in tables.tables if name != "alembic_version"]
    if names:
        with engine.begin() as connection:
            connection.execute(text(f"TRUNCATE {', '.join(names)} CASCADE"))
    yield engine
    engine.dispose()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def storage(tmp_path: Path) -> LocalDiskStorage:
    return LocalDiskStorage(tmp_path / "storage")


@pytest.fixture
def inspector() -> InProcessInspector:
    return InProcessInspector()


@pytest.fixture
def client(
    engine: Engine,
    clock: FakeClock,
    storage: LocalDiskStorage,
    inspector: InProcessInspector,
) -> Iterator[TestClient]:
    app = create_app(engine, clock, storage, inspector)
    with TestClient(app, base_url="https://testserver") as client:
        yield client
