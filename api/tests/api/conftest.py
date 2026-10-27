import pytest
from fastapi.testclient import TestClient

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
