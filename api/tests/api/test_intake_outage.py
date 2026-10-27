from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from ebookdrop.conversion.port import BookFormat
from ebookdrop.inspection.port import InspectorUnavailableError
from tests.api.conftest import count, intake_events, refuse
from tests.samples import epub


class DownInspector:
    def inspect(self, source: Path) -> BookFormat:
        raise InspectorUnavailableError("docker exit 1")


@pytest.fixture
def inspector() -> DownInspector:
    return DownInspector()


def test_upload_while_the_sandbox_is_down_answers_503_and_rejects_nothing(
    client: TestClient, engine: Engine, signed_in_ana: str
) -> None:
    answer = refuse(client, "dune.epub", epub())

    assert answer == (503, {"code": "inspect_unavailable"})
    assert count(engine, "books") == 0
    assert intake_events(engine) == []
