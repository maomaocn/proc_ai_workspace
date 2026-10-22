from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any


class JsonFormatter(logging.Formatter):
    """Serialize application events without inspecting request bodies or credentials."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        event_data = getattr(record, "event_data", None)
        if isinstance(event_data, dict):
            payload.update(
                {key: value for key, value in event_data.items() if key not in payload}
            )
        return json.dumps(payload, ensure_ascii=True, default=str, separators=(",", ":"))


def configure_logging(level: str) -> None:
    """Configure one JSON handler for application loggers; Uvicorn keeps its own access log."""

    resolved_level = getattr(logging, level.upper(), logging.INFO)
    app_logger = logging.getLogger("app")
    app_logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    app_logger.addHandler(handler)
    app_logger.setLevel(resolved_level)
    app_logger.propagate = False
