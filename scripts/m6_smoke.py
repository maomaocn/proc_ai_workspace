#!/usr/bin/env python3
"""Read-only M6 deployment, contract, security, and latency smoke check."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time

import httpx

FULFILLMENT_PATH = "/api/v1/procurements/{request_id}/fulfillment-transition"


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * fraction) - 1))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--username", default="employee")
    parser.add_argument("--password", default="DemoPass123!")
    parser.add_argument("--requests", type=int, default=40)
    parser.add_argument("--p95-limit-ms", type=float, default=1500.0)
    args = parser.parse_args()
    if args.requests < 5:
        parser.error("--requests must be at least 5")

    base_url = args.base_url.rstrip("/")
    checks: dict[str, object] = {}
    with httpx.Client(base_url=base_url, timeout=10, trust_env=False) as client:
        health = client.get("/healthz")
        ready = client.get("/readyz")
        checks["health"] = health.status_code
        checks["ready"] = ready.status_code
        health.raise_for_status()
        ready.raise_for_status()

        openapi = client.get("/openapi.json")
        openapi.raise_for_status()
        paths = openapi.json()["paths"]
        checks["fulfillment_contract"] = FULFILLMENT_PATH in paths
        checks["arbitrary_execution_routes"] = [
            path
            for path in paths
            if any(fragment in path.lower() for fragment in ("shell", "sql", "command-exec"))
        ]

        unauthorized = client.get("/api/v1/procurements")
        invalid_token = client.get(
            "/api/v1/procurements",
            headers={"Authorization": "Bearer invalid-token"},
        )
        checks["unauthorized_status"] = unauthorized.status_code
        checks["invalid_token_status"] = invalid_token.status_code

        login = client.post(
            "/api/v1/auth/login",
            json={"username": args.username, "password": args.password},
        )
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        durations: list[float] = []
        errors = 0
        for _ in range(args.requests):
            started = time.perf_counter()
            response = client.get(
                "/api/v1/procurements?page=1&page_size=20",
                headers=headers,
            )
            durations.append((time.perf_counter() - started) * 1000)
            if response.status_code != 200:
                errors += 1

    p50 = statistics.median(durations)
    p95 = percentile(durations, 0.95)
    result = {
        "base_url": base_url,
        "requests": args.requests,
        "errors": errors,
        "latency_ms": {
            "min": round(min(durations), 2),
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "max": round(max(durations), 2),
        },
        "checks": checks,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    passed = (
        errors == 0
        and p95 <= args.p95_limit_ms
        and checks["health"] == 200
        and checks["ready"] == 200
        and checks["fulfillment_contract"] is True
        and checks["arbitrary_execution_routes"] == []
        and checks["unauthorized_status"] == 401
        and checks["invalid_token_status"] == 401
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
