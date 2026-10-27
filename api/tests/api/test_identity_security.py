from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.api.conftest import PASSWORD, sign_in, sign_up
from tests.conftest import FakeClock

WRONG = "wrong horse battery"


def test_session_cookie_is_httponly_secure_lax_for_14_days(
    client: TestClient, ana: str
) -> None:
    response = client.post(
        "/api/sessions", json={"email": "ana@example.com", "password": PASSWORD}
    )

    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=lax" in cookie
    assert "max-age=1209600" in cookie


def test_request_with_no_or_unknown_session_is_refused(client: TestClient) -> None:
    assert client.get("/api/sessions/current").status_code == 401
    client.cookies.set("session", "made-up")
    assert client.get("/api/sessions/current").status_code == 401


def test_password_is_stored_as_argon2id_hash(
    client: TestClient, engine: Engine, ana: str
) -> None:
    with engine.connect() as connection:
        stored = connection.execute(text("SELECT password_hash FROM accounts")).scalar()

    assert stored.startswith("$argon2id$")
    assert PASSWORD not in stored


def test_password_under_12_characters_is_rejected(client: TestClient) -> None:
    assert sign_up(client, "ana@example.com", "eleven char") == 422


def test_email_with_no_domain_is_rejected(client: TestClient) -> None:
    assert sign_up(client, "ana@") == 422


def test_unknown_email_answers_like_a_wrong_password(client: TestClient) -> None:
    response = client.post(
        "/api/sessions", json={"email": "nobody@example.com", "password": PASSWORD}
    )

    assert response.status_code == 401
    assert response.json() == {"code": "wrong_email_or_password"}


def test_eleventh_sign_in_in_one_hour_answers_429_even_with_right_password(
    client: TestClient, clock: FakeClock, ana: str
) -> None:
    for _ in range(10):
        assert sign_in(client, " ANA@example.com", WRONG) == 401

    response = client.post(
        "/api/sessions", json={"email": "ana@example.com", "password": PASSWORD}
    )

    assert response.status_code == 429
    assert response.json() == {"code": "too_many_attempts"}


def test_sign_in_works_again_one_hour_after_the_first_failure(
    client: TestClient, clock: FakeClock, ana: str
) -> None:
    for _ in range(10):
        assert sign_in(client, ana, WRONG) == 401
        clock.advance(timedelta(minutes=1))
    assert sign_in(client, ana) == 429

    clock.advance(timedelta(minutes=50))

    assert sign_in(client, ana) == 204
