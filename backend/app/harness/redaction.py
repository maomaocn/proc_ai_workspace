from __future__ import annotations

import json
import re
from typing import Any

from app.core.config import settings

_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
}
_SECRET_PATTERNS = (
    re.compile(r"(?i)bearer\s+[a-z0-9._~-]+"),
    re.compile(r"\bsk-[a-zA-Z0-9_-]{8,}\b"),
)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if str(key).lower() in _SENSITIVE_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, str):
        result = value
        for pattern in _SECRET_PATTERNS:
            result = pattern.sub("[REDACTED]", result)
        return result
    return value


def summarize(value: Any) -> str:
    payload = json.dumps(redact(value), ensure_ascii=False, sort_keys=True, default=str)
    limit = settings.agent_trace_summary_max_chars
    if len(payload) <= limit:
        return payload
    return f"{payload[: limit - 14]}...[TRUNCATED]"
