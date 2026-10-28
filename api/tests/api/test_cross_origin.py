import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import sign_in

SIBLING = {"Origin": "https://evil.testserver"}
OWN = {"Origin": "https://testserver"}


def test_account_delete_from_another_origin_is_refused_and_the_account_stays(
    client: TestClient, signed_in_ana: str
) -> None:
    response = client.delete("/api/accounts/me", headers=SIBLING)

    assert (response.status_code, response.json()) == (403, {"code": "cross_origin"})
    assert client.get("/api/sessions/current").status_code == 200
    assert sign_in(client, signed_in_ana) == 204


@pytest.mark.parametrize(
    ("method", "path"),
    [("POST", "/api/books"), ("DELETE", "/api/sessions/current")],
)
def test_each_change_from_another_origin_is_refused(
    client: TestClient, signed_in_ana: str, method: str, path: str
) -> None:
    response = client.request(method, path, headers=SIBLING)

    assert response.status_code == 403


def test_account_delete_from_its_own_origin_goes_through(
    client: TestClient, signed_in_ana: str
) -> None:
    assert client.delete("/api/accounts/me", headers=OWN).status_code == 204


def test_read_from_another_origin_is_not_refused(
    client: TestClient, signed_in_ana: str
) -> None:
    assert client.get("/api/sessions/current", headers=SIBLING).status_code == 200
