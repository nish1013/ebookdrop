import threading

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.api.conftest import PASSWORD, sign_in


def test_s1_ac1_new_email_gets_an_account_and_a_session(client: TestClient) -> None:
    response = client.post(
        "/api/accounts", json={"email": "ana@example.com", "password": PASSWORD}
    )

    assert response.status_code == 201
    assert response.json() == {"email": "ana@example.com"}
    assert sign_in(client, "ana@example.com") == 204
    assert client.get("/api/sessions/current").json() == {"email": "ana@example.com"}


def test_s1_ac2_taken_email_is_rejected_whatever_its_case_and_spaces(
    client: TestClient, ana: str
) -> None:
    response = client.post(
        "/api/accounts", json={"email": " ANA@example.com", "password": PASSWORD}
    )

    assert response.status_code == 409
    assert response.json() == {"code": "email_taken"}


def test_s1_ac3_two_sign_ups_in_the_same_second_make_one_account(
    client: TestClient, engine: Engine
) -> None:
    start = threading.Barrier(2)
    statuses: list[int] = []

    def sign_up_ana() -> None:
        with TestClient(client.app, base_url="https://testserver") as own:
            start.wait()
            response = own.post(
                "/api/accounts", json={"email": "ana@example.com", "password": PASSWORD}
            )
            statuses.append(response.status_code)

    threads = [threading.Thread(target=sign_up_ana) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(statuses) == [201, 409]
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM accounts")).scalar() == 1
