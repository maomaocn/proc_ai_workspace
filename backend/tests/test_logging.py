import json
import logging
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.core.logging import JsonFormatter


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(main_module.app) as test_client:
        yield test_client


def test_json_formatter_serializes_structured_event() -> None:
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request.completed",
        args=(),
        exc_info=None,
    )
    request_id = uuid.uuid4()
    record.event_data = {
        "request_id": request_id,
        "status_code": 200,
        "duration_ms": 3.25,
    }

    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "request.completed"
    assert payload["level"] == "INFO"
    assert payload["request_id"] == str(request_id)
    assert payload["status_code"] == 200


def test_request_log_uses_route_template_and_omits_query(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[tuple[str, dict]] = []

    def capture(message: str, *, extra: dict) -> None:
        captured.append((message, extra["event_data"]))

    monkeypatch.setattr(main_module.logger, "info", capture)
    response = client.get("/healthz?access_token=must-not-be-logged")

    assert response.status_code == 200
    message, event = captured[-1]
    assert message == "request.completed"
    assert event["request_id"] == response.headers["X-Request-ID"]
    assert event["route"] == "/healthz"
    assert event["method"] == "GET"
    assert event["status_code"] == 200
    assert "access_token" not in json.dumps(event)
