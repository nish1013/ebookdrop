from fastapi.testclient import TestClient

from tests.api.conftest import PASSWORD


def test_s2_ac1_right_password_starts_a_session(client: TestClient, ana: str) -> None:
    response = client.post(
        "/api/sessions", json={"email": "ana@example.com", "password": PASSWORD}
    )

    assert response.status_code == 204
    assert client.get("/api/sessions/current").json() == {"email": "ana@example.com"}


def test_s2_ac2_wrong_password_is_rejected(client: TestClient, ana: str) -> None:
    response = client.post(
        "/api/sessions",
        json={"email": "ana@example.com", "password": "wrong horse battery"},
    )

    assert response.status_code == 401
    assert response.json() == {"code": "wrong_email_or_password"}
    assert client.get("/api/sessions/current").status_code == 401
