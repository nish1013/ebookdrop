from datetime import timedelta

from fastapi.testclient import TestClient

from tests.api.conftest import sign_in
from tests.conftest import FakeClock


def test_s3_ac1_old_session_is_refused_after_sign_out(
    client: TestClient, ana: str
) -> None:
    assert sign_in(client, ana) == 204
    old_session = client.cookies["session"]

    assert client.delete("/api/sessions/current").status_code == 204

    client.cookies.set("session", old_session)
    assert client.get("/api/sessions/current").status_code == 401


def test_s3_ac2_session_ends_14_days_after_sign_in(
    client: TestClient, clock: FakeClock, ana: str
) -> None:
    assert sign_in(client, ana) == 204

    clock.advance(timedelta(days=14) - timedelta(seconds=1))
    assert client.get("/api/sessions/current").status_code == 200

    clock.advance(timedelta(seconds=1))
    assert client.get("/api/sessions/current").status_code == 401
