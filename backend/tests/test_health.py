import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.db import session
from app.db.session import check_database
from app.main import app


class FailingConnection:
    async def __aenter__(self) -> None:
        raise SQLAlchemyError("database unavailable")

    async def __aexit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        return None


class FailingEngine:
    def connect(self) -> FailingConnection:
        return FailingConnection()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_healthz(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "Enterprise AI Agent Hub"


@pytest.mark.parametrize(
    ("database_ready", "expected_status_code", "expected_status", "expected_database"),
    [
        (True, 200, "ready", "up"),
        (False, 503, "not_ready", "down"),
    ],
)
def test_readyz(
    client: TestClient,
    database_ready: bool,
    expected_status_code: int,
    expected_status: str,
    expected_database: str,
) -> None:
    async def readiness_override() -> bool:
        return database_ready

    app.dependency_overrides[check_database] = readiness_override
    response = client.get("/readyz")

    assert response.status_code == expected_status_code
    assert response.json()["status"] == expected_status
    assert response.json()["dependencies"]["database"] == expected_database


def test_openapi_exposes_system_endpoints(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/healthz" in paths
    assert "/readyz" in paths


def test_database_check_returns_false_when_connection_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(session, "engine", FailingEngine())

    assert asyncio.run(session.check_database()) is False
