import os
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.seed import DEMO_PASSWORD, seed_demo_data
from app.db.session import engine, get_session
from app.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS", "false").lower() != "true",
    reason="set RUN_DB_TESTS=true to run PostgreSQL integration tests",
)


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    await seed_demo_data()
    async with engine.connect() as connection:
        transaction = await connection.begin()
        db_session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async def override_session() -> AsyncIterator[AsyncSession]:
            yield db_session

        app.dependency_overrides[get_session] = override_session
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as test_client:
            yield test_client
        app.dependency_overrides.clear()
        await db_session.close()
        await transaction.rollback()


async def login(client: httpx.AsyncClient, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_authentication_and_rbac(client: httpx.AsyncClient) -> None:
    unauthorized = await client.get("/api/v1/auth/me")
    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"]["code"] == "UNAUTHORIZED"

    employee_token = await login(client, "employee")
    forbidden = await client.get("/api/v1/admin/users", headers=headers(employee_token))
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"

    tech_token = await login(client, "techadmin")
    tech_forbidden = await client.get("/api/v1/admin/users", headers=headers(tech_token))
    assert tech_forbidden.status_code == 403

    admin_token = await login(client, "admin")
    allowed = await client.get("/api/v1/admin/users", headers=headers(admin_token))
    assert allowed.status_code == 200
    assert allowed.json()["total"] >= 5
    assert all("password_hash" not in item for item in allowed.json()["items"])


@pytest.mark.asyncio
async def test_chat_session_isolation(client: httpx.AsyncClient) -> None:
    employee_token = await login(client, "employee")
    created = await client.post(
        "/api/v1/chat/sessions",
        headers=headers(employee_token),
        json={"title": "员工私有会话"},
    )
    assert created.status_code == 201
    session_id = created.json()["id"]

    approver_token = await login(client, "approver")
    cross_user = await client.get(
        f"/api/v1/chat/sessions/{session_id}", headers=headers(approver_token)
    )
    assert cross_user.status_code == 403

    approver_sessions = await client.get(
        "/api/v1/chat/sessions", headers=headers(approver_token)
    )
    assert session_id not in {item["id"] for item in approver_sessions.json()["items"]}


@pytest.mark.asyncio
async def test_intent_flow_requires_confirmation_without_procurement_side_effect(
    client: httpx.AsyncClient,
) -> None:
    token = await login(client, "employee")
    created = await client.post(
        "/api/v1/chat/sessions", headers=headers(token), json={"title": "笔记本采购"}
    )
    session_id = created.json()["id"]

    turn = await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        headers=headers(token),
        json={"content": "采购10台笔记本，每台6000元"},
    )
    assert turn.status_code == 200
    body = turn.json()
    assert body["parse_result"]["intent"]["quantity"] == 10
    assert body["parse_result"]["intent"]["unit_price_limit"] == "6000.00"
    assert body["parse_result"]["intent"]["total_budget"] == "60000.00"
    assert body["parse_result"]["missing_fields"] == ["purpose"]
    assistant_message_id = body["assistant_message"]["id"]

    incomplete = await client.post(
        f"/api/v1/chat/messages/{assistant_message_id}/confirm-intent",
        headers=headers(token),
        json={"intent": body["parse_result"]["intent"]},
    )
    assert incomplete.status_code == 422
    assert incomplete.json()["error"]["code"] == "BUSINESS_RULE_VIOLATION"

    completed_intent = {**body["parse_result"]["intent"], "purpose": "研发办公"}
    confirmed = await client.post(
        f"/api/v1/chat/messages/{assistant_message_id}/confirm-intent",
        headers=headers(token),
        json={"intent": completed_intent},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["message"]["status"] == "CONFIRMED"
    assert confirmed.json()["purchase_request_created"] is False

    messages = await client.get(
        f"/api/v1/chat/sessions/{session_id}/messages", headers=headers(token)
    )
    assert messages.status_code == 200
    assert [item["sender"] for item in messages.json()["items"]] == ["USER", "ASSISTANT"]
