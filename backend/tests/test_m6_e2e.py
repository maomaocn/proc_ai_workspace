import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import workflow_runtime
from app.core.config import settings
from app.db.seed import DEMO_PASSWORD, seed_demo_data
from app.db.session import engine, get_session
from app.main import app
from app.models.approval import AgentRun
from app.rag.vector_store import get_vector_store

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS", "false").lower() != "true",
    reason="set RUN_DB_TESTS=true to run PostgreSQL integration tests",
)


@pytest_asyncio.fixture
async def context(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    await seed_demo_data()
    old_chroma_path = settings.chroma_path
    old_collection_name = settings.chroma_collection_name
    settings.chroma_path = str(tmp_path / "chroma")
    settings.chroma_collection_name = f"test-m6-{uuid.uuid4().hex}"
    get_vector_store.cache_clear()

    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async def override_session() -> AsyncIterator[AsyncSession]:
            yield session

        existing_threads = set((await session.scalars(select(AgentRun.graph_thread_id))).all())
        app.dependency_overrides[get_session] = override_session
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                yield client
        finally:
            current_threads = set((await session.scalars(select(AgentRun.graph_thread_id))).all())
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()
            for thread_id in current_threads - existing_threads:
                await workflow_runtime.delete_thread(thread_id)

    get_vector_store.cache_clear()
    settings.chroma_path = old_chroma_path
    settings.chroma_collection_name = old_collection_name


async def login(client: httpx.AsyncClient, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": DEMO_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str, key: uuid.UUID | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if key is not None:
        headers["Idempotency-Key"] = str(key)
    return headers


async def approved_purchase(client: httpx.AsyncClient, employee: str) -> dict:
    payload = {
        "title": f"M6 全链路验收 {uuid.uuid4().hex[:8]}",
        "category": "笔记本电脑",
        "item_description": "研发办公笔记本",
        "quantity": 10,
        "unit_price_limit": "6000.00",
        "purpose": "M6 全链路演示",
        "priority": "NORMAL",
        "notes": "仅使用 DEMO 库存与报价",
    }
    created = await client.post("/api/v1/procurements", headers=auth(employee), json=payload)
    assert created.status_code == 201, created.text
    planned = await client.post(
        f"/api/v1/procurements/{created.json()['id']}/plan", headers=auth(employee)
    )
    assert planned.status_code == 200, planned.text
    draft = planned.json()["procurement"]
    submitted = await client.post(
        f"/api/v1/procurements/{draft['id']}/submit",
        headers=auth(employee, uuid.uuid4()),
        json={"version": draft["version"]},
    )
    assert submitted.status_code == 200, submitted.text

    manager = await login(client, "manager")
    approver = await login(client, "approver")
    first, second = submitted.json()["approval_tasks"]
    first_decision = await client.post(
        f"/api/v1/approvals/tasks/{first['id']}/decision",
        headers=auth(manager, uuid.uuid4()),
        json={"action": "APPROVE", "comment": "部门预算和用途已核验"},
    )
    assert first_decision.status_code == 200, first_decision.text
    final_decision = await client.post(
        f"/api/v1/approvals/tasks/{second['id']}/decision",
        headers=auth(approver, uuid.uuid4()),
        json={"action": "APPROVE", "comment": "财务预算已核验"},
    )
    assert final_decision.status_code == 200, final_decision.text
    assert final_decision.json()["purchase_status"] == "APPROVED"
    return (
        await client.get(f"/api/v1/procurements/{draft['id']}", headers=auth(employee))
    ).json()


@pytest.mark.asyncio
async def test_complete_mock_procurement_fulfillment_e2e(context: httpx.AsyncClient) -> None:
    employee = await login(context, "employee")
    procurement = await login(context, "procurement")
    purchase = await approved_purchase(context, employee)

    authorized = await context.get(
        "/api/v1/procurements?page=1&page_size=100&status=APPROVED",
        headers=auth(procurement),
    )
    assert authorized.status_code == 200
    assert purchase["id"] in {item["id"] for item in authorized.json()["items"]}

    expected = ["ORDERED", "RECEIVED", "CLOSED"]
    for target in expected:
        response = await context.post(
            f"/api/v1/procurements/{purchase['id']}/fulfillment-transition",
            headers=auth(procurement, uuid.uuid4()),
            json={
                "target_status": target,
                "version": purchase["version"],
                "note": f"M6 模拟履约：{target}",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["source"] == "DEMO"
        assert response.json()["previous_status"] == purchase["status"]
        purchase["status"] = target
        purchase["version"] = response.json()["version"]

    detail = await context.get(
        f"/api/v1/procurements/{purchase['id']}", headers=auth(employee)
    )
    assert detail.status_code == 200
    assert detail.json()["status"] == "CLOSED"
    actions = [event["action"] for event in detail.json()["audit_events"]]
    assert actions[-3:] == [
        "FULFILLMENT_ORDERED",
        "FULFILLMENT_RECEIVED",
        "FULFILLMENT_CLOSED",
    ]


@pytest.mark.asyncio
async def test_fulfillment_permissions_sequence_version_and_idempotency(
    context: httpx.AsyncClient,
) -> None:
    employee = await login(context, "employee")
    procurement = await login(context, "procurement")
    admin = await login(context, "admin")
    techadmin = await login(context, "techadmin")

    created = await context.post(
        "/api/v1/procurements",
        headers=auth(employee),
        json={
            "title": "未审批履约拒绝",
            "category": "显示器",
            "item_description": "办公显示器",
            "quantity": 1,
            "unit_price_limit": "2000.00",
            "purpose": "权限验收",
            "priority": "NORMAL",
        },
    )
    draft = created.json()
    denied_draft = await context.post(
        f"/api/v1/procurements/{draft['id']}/fulfillment-transition",
        headers=auth(procurement, uuid.uuid4()),
        json={"target_status": "ORDERED", "version": draft["version"]},
    )
    assert denied_draft.status_code == 409
    assert denied_draft.json()["error"]["code"] == "STATE_CONFLICT"

    purchase = await approved_purchase(context, employee)
    for token in (employee, admin, techadmin):
        denied = await context.post(
            f"/api/v1/procurements/{purchase['id']}/fulfillment-transition",
            headers=auth(token, uuid.uuid4()),
            json={"target_status": "ORDERED", "version": purchase["version"]},
        )
        assert denied.status_code == 403

    skipped = await context.post(
        f"/api/v1/procurements/{purchase['id']}/fulfillment-transition",
        headers=auth(procurement, uuid.uuid4()),
        json={"target_status": "RECEIVED", "version": purchase["version"]},
    )
    assert skipped.status_code == 409
    assert skipped.json()["error"]["details"]["allowed_target"] == "ORDERED"

    key = uuid.uuid4()
    ordered_payload = {"target_status": "ORDERED", "version": purchase["version"]}
    ordered = await context.post(
        f"/api/v1/procurements/{purchase['id']}/fulfillment-transition",
        headers=auth(procurement, key),
        json=ordered_payload,
    )
    assert ordered.status_code == 200
    replay = await context.post(
        f"/api/v1/procurements/{purchase['id']}/fulfillment-transition",
        headers=auth(procurement, key),
        json=ordered_payload,
    )
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True

    conflict = await context.post(
        f"/api/v1/procurements/{purchase['id']}/fulfillment-transition",
        headers=auth(procurement, key),
        json={"target_status": "RECEIVED", "version": ordered.json()["version"]},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

    stale = await context.post(
        f"/api/v1/procurements/{purchase['id']}/fulfillment-transition",
        headers=auth(procurement, uuid.uuid4()),
        json={"target_status": "RECEIVED", "version": purchase["version"]},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["details"]["current_version"] == ordered.json()["version"]


@pytest.mark.asyncio
async def test_m6_openapi_contract_and_no_arbitrary_execution_surface(
    context: httpx.AsyncClient,
) -> None:
    response = await context.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    path = schema["paths"]["/api/v1/procurements/{request_id}/fulfillment-transition"]
    assert set(path) == {"post"}
    operation = path["post"]
    assert operation["security"] == [{"HTTPBearer": []}]
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    assert request_schema["$ref"].endswith("/FulfillmentTransitionRequest")
    assert set(schema["components"]["schemas"]["FulfillmentTransitionRequest"]["required"]) == {
        "target_status",
        "version",
    }
    assert not any(
        forbidden in route.lower()
        for route in schema["paths"]
        for forbidden in ("shell", "sql", "command-exec")
    )

    unauthenticated = await context.get("/api/v1/procurements")
    assert unauthenticated.status_code == 401
    fake_token = await context.get(
        "/api/v1/procurements", headers={"Authorization": "Bearer invalid-token"}
    )
    assert fake_token.status_code == 401


@pytest.mark.asyncio
async def test_chat_run_persists_stream_events_and_resume_is_read_only(
    context: httpx.AsyncClient,
) -> None:
    employee = await login(context, "employee")
    created = await context.post(
        "/api/v1/chat/sessions",
        headers=auth(employee),
        json={"title": "M6 SSE 验收"},
    )
    assert created.status_code == 201
    session_id = created.json()["id"]
    turn = await context.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        headers=auth(employee),
        json={"content": "采购10台笔记本，每台6000元，用于研发办公"},
    )
    assert turn.status_code == 200, turn.text
    run_id = turn.json()["run_id"]

    runs = await context.get(
        "/api/v1/agent-runs?run_type=CHAT&page=1&page_size=100",
        headers=auth(employee),
    )
    assert runs.status_code == 403
    detail = await context.get(f"/api/v1/agent-runs/{run_id}", headers=auth(employee))
    assert detail.status_code == 200
    assert detail.json()["run_type"] == "CHAT"

    events = await context.get(f"/api/v1/agent-runs/{run_id}/events", headers=auth(employee))
    assert events.status_code == 200
    for event_type in (
        "run.started",
        "node.started",
        "message.delta",
        "node.completed",
        "run.completed",
    ):
        assert f"event: {event_type}" in events.text

    resumed = await context.get(
        f"/api/v1/agent-runs/{run_id}/events",
        headers={**auth(employee), "Last-Event-ID": "3"},
    )
    assert resumed.status_code == 200
    assert "event: run.started" not in resumed.text
    assert "event: node.completed" in resumed.text
    assert "event: run.completed" in resumed.text

    messages = await context.get(
        f"/api/v1/chat/sessions/{session_id}/messages", headers=auth(employee)
    )
    assert messages.status_code == 200
    assert messages.json()["total"] == 2
