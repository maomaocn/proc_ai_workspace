import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.db.seed import DEMO_PASSWORD, seed_demo_data
from app.db.session import engine, get_session
from app.harness import AgentCall, AgentRunner
from app.main import app
from app.mcp.client import mcp_client
from app.models.approval import AgentRun, ToolPolicy
from app.models.identity import User
from app.rag.vector_store import get_vector_store
from app.tools.registry import ToolDefinition, ToolRegistry

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS", "false").lower() != "true",
    reason="set RUN_DB_TESTS=true to run PostgreSQL integration tests",
)


@pytest_asyncio.fixture
async def context(tmp_path: Path) -> AsyncIterator[tuple[httpx.AsyncClient, AsyncSession]]:
    await seed_demo_data()
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async def override_session() -> AsyncIterator[AsyncSession]:
            yield session

        app.dependency_overrides[get_session] = override_session
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                yield client, session
        finally:
            app.dependency_overrides.clear()
            await session.close()
            await transaction.rollback()
            get_vector_store.cache_clear()


async def login(client: httpx.AsyncClient, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_real_stdio_mcp_discovers_and_queries_demo_inventory() -> None:
    name, version, tools = await mcp_client.discover()
    assert name == "enterprise-ai-agent-hub-mcp"
    assert version
    assert {tool.name for tool in tools} == {"inventory_search", "supplier_quote"}

    result = await mcp_client.call(
        "inventory_search", {"category": "笔记本电脑", "min_qty": 10, "limit": 10}
    )
    assert result["tool_source"] == "MCP_STDIO"
    assert result["items"]
    assert all(item["available_qty"] >= 10 for item in result["items"])


@pytest.mark.asyncio
async def test_mcp_tool_center_harness_trace_and_sse_resume(
    context: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _ = context
    tech = await login(client, "techadmin")
    employee = await login(client, "employee")

    denied = await client.get("/api/v1/mcp/tools", headers=auth(employee))
    assert denied.status_code == 403

    servers = await client.get("/api/v1/mcp/servers", headers=auth(tech))
    assert servers.status_code == 200, servers.text
    assert servers.json()[0]["health_status"] == "HEALTHY"
    assert servers.json()[0]["tool_count"] == 2

    tools = await client.get("/api/v1/mcp/tools", headers=auth(tech))
    assert tools.status_code == 200
    assert {tool["id"] for tool in tools.json()} == {
        "mcp.inventory.search",
        "mcp.supplier.quote",
    }
    assert all(tool["read_only"] for tool in tools.json())

    tested = await client.post(
        "/api/v1/mcp/tools/mcp.inventory.search/test",
        headers=auth(tech),
        json={"arguments": {"category": "笔记本电脑", "min_qty": 1, "limit": 2}},
    )
    assert tested.status_code == 200, tested.text
    body = tested.json()
    assert body["source"] == "MCP_STDIO"
    assert body["run"]["status"] == "SUCCEEDED"
    assert len(body["output"]["items"]) == 2

    run_id = body["run"]["id"]
    detail = await client.get(f"/api/v1/agent-runs/{run_id}", headers=auth(tech))
    assert detail.status_code == 200
    assert detail.json()["steps"][0]["node_name"] == "mcp_tool_call"
    assert detail.json()["steps"][0]["output_summary"]

    events = await client.get(f"/api/v1/agent-runs/{run_id}/events", headers=auth(tech))
    assert events.status_code == 200
    assert "event: run.started" in events.text
    assert "event: run.completed" in events.text
    resumed = await client.get(
        f"/api/v1/agent-runs/{run_id}/events",
        headers={**auth(tech), "Last-Event-ID": "2"},
    )
    assert "id: 1\n" not in resumed.text
    assert "id: 2\n" not in resumed.text
    assert "event: run.completed" in resumed.text


class SlowToolInput(BaseModel):
    value: str
    api_key: str | None = None


async def slow_executor(_: AsyncSession, __: User, ___: BaseModel) -> dict:
    await asyncio.sleep(0.05)
    return {"ok": True}


@pytest.mark.asyncio
async def test_harness_timeout_step_limit_policy_denial_and_redaction(
    context: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    _, session = context
    tech = await session.scalar(
        select(User)
        .where(User.username == "techadmin")
        .options(selectinload(User.role_assignments))
    )
    assert tech is not None

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="test.slow",
            description="timeout test",
            input_model=SlowToolInput,
            allowed_roles=frozenset({"TECH_ADMIN"}),
            executor=slow_executor,
            timeout_ms=5,
            max_calls_per_run=2,
        )
    )
    session.add(
        ToolPolicy(
            tool_name="test.slow",
            allowed_roles=["TECH_ADMIN"],
            read_only=True,
            enabled=True,
            max_calls_per_run=2,
        )
    )
    await session.flush()
    runner = AgentRunner(registry)

    with pytest.raises(AppError) as timed_out:
        await runner.run(
            session,
            tech,
            [AgentCall("test.slow", {"value": "x", "api_key": "sk-secret-value"})],
            allowed_tools={"test.slow"},
            max_steps=3,
        )
    assert timed_out.value.code == "TOOL_TIMEOUT"
    timeout_run = await session.get(AgentRun, uuid.UUID(timed_out.value.details["run_id"]))
    assert timeout_run is not None
    await session.refresh(timeout_run, ["steps"])
    assert timeout_run.status == "FAILED"
    assert timeout_run.retry_count == 1
    assert len(timeout_run.steps) == 2
    assert all("sk-secret-value" not in (step.input_summary or "") for step in timeout_run.steps)
    assert all("[REDACTED]" in (step.input_summary or "") for step in timeout_run.steps)

    with pytest.raises(AppError) as denied:
        await runner.run(
            session,
            tech,
            [AgentCall("test.slow", {"value": "x"})],
            allowed_tools=set(),
        )
    assert denied.value.code == "TOOL_NOT_ALLOWED"

    with pytest.raises(AppError) as limited:
        await runner.run(
            session,
            tech,
            [AgentCall("test.slow", {"value": "1"}), AgentCall("test.slow", {"value": "2"})],
            allowed_tools={"test.slow"},
            max_steps=1,
        )
    assert limited.value.code == "STEP_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_workflow_endpoint_uses_persisted_m4_nodes(
    context: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _ = context
    employee = await login(client, "employee")
    admin = await login(client, "admin")
    created = await client.post(
        "/api/v1/procurements",
        headers=auth(employee),
        json={
            "title": f"M5 Workflow {uuid.uuid4().hex[:8]}",
            "category": "笔记本电脑",
            "item_description": "研发办公笔记本",
            "quantity": 1,
            "unit_price_limit": "6000.00",
            "purpose": "研发办公",
            "priority": "NORMAL",
        },
    )
    assert created.status_code == 201
    request_id = created.json()["id"]
    planned = await client.post(
        f"/api/v1/procurements/{request_id}/plan", headers=auth(employee)
    )
    assert planned.status_code == 200, planned.text
    submitted = await client.post(
        f"/api/v1/procurements/{request_id}/submit",
        headers={**auth(employee), "Idempotency-Key": str(uuid.uuid4())},
        json={"version": planned.json()["procurement"]["version"]},
    )
    assert submitted.status_code == 200, submitted.text
    run_id = submitted.json()["run"]["id"]

    workflow = await client.get(f"/api/v1/workflows/runs/{run_id}", headers=auth(admin))
    assert workflow.status_code == 200, workflow.text
    assert workflow.json()["run"]["status"] == "WAITING_APPROVAL"
    assert [node["node_name"] for node in workflow.json()["nodes"]] == [
        "resolve_approval_chain",
        "await_approval_stage_1",
    ]
    assert len(workflow.json()["edges"]) == 1
