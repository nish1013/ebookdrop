from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from ebookdrop.library.domain import QUOTA_BYTES
from tests.api.conftest import count, fill_library, refuse, upload
from tests.samples import epub

DUNE = epub()


def stored_files(tmp_path: Path) -> list[str]:
    root = tmp_path / "storage"
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


@pytest.fixture
def failing_job_insert(engine: Engine) -> Iterator[None]:
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE FUNCTION refuse_job() RETURNS trigger LANGUAGE plpgsql AS"
                " $$ BEGIN RAISE EXCEPTION 'job insert refused'; END $$;"
                " CREATE TRIGGER refuse_job BEFORE INSERT ON conversion_jobs"
                " FOR EACH ROW EXECUTE FUNCTION refuse_job();"
            )
        )
    yield
    with engine.begin() as connection:
        connection.execute(
            text(
                "DROP TRIGGER refuse_job ON conversion_jobs;"
                " DROP FUNCTION refuse_job();"
            )
        )


def test_duplicate_upload_leaves_no_stored_file(
    client: TestClient, tmp_path: Path, signed_in_ana: str
) -> None:
    first = upload(client, "dune.epub", DUNE)

    assert refuse(client, "dune-copy.epub", DUNE)[0] == 409

    assert stored_files(tmp_path) == [f"books/{first['id']}/original"]


def test_over_quota_upload_leaves_no_stored_file(
    client: TestClient, engine: Engine, tmp_path: Path, signed_in_ana: str
) -> None:
    fill_library(engine, signed_in_ana, QUOTA_BYTES - len(DUNE) + 1, 50 * 1024**2)

    assert refuse(client, "dune.epub", DUNE) == (422, {"code": "over_quota"})

    assert stored_files(tmp_path) == []


def test_rolled_back_upload_leaves_no_stored_file(
    client: TestClient,
    engine: Engine,
    tmp_path: Path,
    signed_in_ana: str,
    failing_job_insert: None,
) -> None:
    with pytest.raises(DBAPIError):
        client.post("/api/books", files={"file": ("dune.epub", DUNE)})

    assert count(engine, "books") == 0
    assert stored_files(tmp_path) == []
