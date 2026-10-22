import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import AppError
from app.db.seed import DEMO_PASSWORD, seed_demo_data
from app.db.session import engine, get_session
from app.main import app
from app.models.identity import User
from app.rag.vector_store import get_vector_store
from app.tools.registry import tool_registry

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS", "false").lower() != "true",
    reason="set RUN_DB_TESTS=true to run PostgreSQL integration tests",
)


@pytest_asyncio.fixture
async def client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    await seed_demo_data()
    old_chroma_path = settings.chroma_path
    old_collection_name = settings.chroma_collection_name
    settings.chroma_path = str(tmp_path / "chroma")
    settings.chroma_collection_name = f"test-m3-{uuid.uuid4().hex}"
    get_vector_store.cache_clear()

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

    get_vector_store.cache_clear()
    settings.chroma_path = old_chroma_path
    settings.chroma_collection_name = old_collection_name


async def login(client: httpx.AsyncClient, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def draft_payload() -> dict[str, object]:
    return {
        "title": "研发笔记本采购",
        "category": "笔记本电脑",
        "item_description": "研发办公笔记本",
        "quantity": 10,
        "unit_price_limit": "6000.00",
        "purpose": "研发办公",
        "priority": "NORMAL",
        "notes": "演示采购",
    }


@pytest.mark.asyncio
async def test_seed_inventory_supplier_permissions_and_validation(
    client: httpx.AsyncClient,
) -> None:
    employee = await login(client, "employee")
    procurement = await login(client, "procurement")
    admin = await login(client, "admin")

    inventory = await client.get(
        "/api/v1/inventory/items?page=1&page_size=100", headers=headers(employee)
    )
    assert inventory.status_code == 200
    assert inventory.json()["total"] >= 3
    thinkbook = next(item for item in inventory.json()["items"] if item["sku"] == "LT-THINK-14")
    assert thinkbook["reference_price"] == "5799.00"
    assert thinkbook["available_qty"] == 25

    employee_write = await client.post(
        "/api/v1/inventory/items",
        headers=headers(employee),
        json={
            "sku": "NO-PERMISSION",
            "category": "测试",
            "model": "测试",
            "available_qty": 1,
            "reference_price": "1.00",
        },
    )
    assert employee_write.status_code == 403

    invalid = await client.post(
        "/api/v1/inventory/items",
        headers=headers(admin),
        json={
            "sku": "INVALID-QTY",
            "category": "测试",
            "model": "测试",
            "available_qty": -1,
            "reference_price": "1.00",
        },
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"

    employee_suppliers = await client.get("/api/v1/suppliers", headers=headers(employee))
    assert employee_suppliers.status_code == 403
    suppliers = await client.get(
        "/api/v1/suppliers?page=1&page_size=100", headers=headers(procurement)
    )
    assert suppliers.status_code == 200
    assert suppliers.json()["total"] >= 2
    assert all(item["demo_data"] for item in suppliers.json()["items"])

    quotes = await client.get(
        "/api/v1/supplier-quotes?page=1&page_size=100", headers=headers(procurement)
    )
    assert quotes.status_code == 200
    assert quotes.json()["total"] >= 4
    assert {item["source_type"] for item in quotes.json()["items"]} == {"DEMO"}


@pytest.mark.asyncio
async def test_procurement_decimal_ownership_version_and_plan(client: httpx.AsyncClient) -> None:
    employee = await login(client, "employee")
    approver = await login(client, "approver")
    admin = await login(client, "admin")

    created = await client.post(
        "/api/v1/procurements",
        headers=headers(employee),
        json={**draft_payload(), "total_budget": "1.00"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    request_id = body["id"]
    assert body["total_budget"] == "60000.00"
    assert body["status"] == "DRAFT"
    assert body["version"] == 0

    forbidden = await client.get(
        f"/api/v1/procurements/{request_id}", headers=headers(approver)
    )
    assert forbidden.status_code == 403
    admin_read = await client.get(
        f"/api/v1/procurements/{request_id}", headers=headers(admin)
    )
    assert admin_read.status_code == 200

    recalculated = await client.patch(
        f"/api/v1/procurements/{request_id}",
        headers=headers(employee),
        json={"version": 0, "quantity": 9, "total_budget": "1.00"},
    )
    assert recalculated.status_code == 200, recalculated.text
    assert recalculated.json()["quantity"] == 9
    assert recalculated.json()["total_budget"] == "54000.00"
    assert recalculated.json()["version"] == 1

    updated = await client.patch(
        f"/api/v1/procurements/{request_id}",
        headers=headers(employee),
        json={"version": 1, "notes": "已复核预算"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    stale = await client.patch(
        f"/api/v1/procurements/{request_id}",
        headers=headers(employee),
        json={"version": 0, "notes": "过期修改"},
    )
    assert stale.status_code == 409

    plan = await client.post(
        f"/api/v1/procurements/{request_id}/plan", headers=headers(employee)
    )
    assert plan.status_code == 200, plan.text
    plan_body = plan.json()
    assert plan_body["source"] == "DEMO"
    assert plan_body["procurement"]["candidates"]
    cheapest = plan_body["procurement"]["candidates"][0]
    assert cheapest["unit_price"] == "5680.00"
    assert cheapest["total_price"] == "51120.00"
    assert cheapest["stock_sufficient"] is True
    assert cheapest["within_unit_limit"] is True
    assert cheapest["source_quote"]["source_type"] == "DEMO"
    tool_names = {item["name"] for item in plan_body["tool_calls"]}
    assert {"inventory.search", "supplier.quote", "policy.search"} <= tool_names


@pytest.mark.asyncio
async def test_tool_registry_rejects_invalid_input_and_unauthorized_role(
    client: httpx.AsyncClient,
) -> None:
    async with engine.connect() as connection:
        session = AsyncSession(bind=connection, expire_on_commit=False)
        employee = await session.scalar(
            select(User)
            .where(User.username == "employee")
            .options(selectinload(User.role_assignments))
        )
        techadmin = await session.scalar(
            select(User)
            .where(User.username == "techadmin")
            .options(selectinload(User.role_assignments))
        )
        assert employee is not None and techadmin is not None

        with pytest.raises(AppError) as invalid:
            await tool_registry.invoke(
                "inventory.search", {"category": "笔记本电脑", "min_qty": -1}, employee, session
            )
        assert invalid.value.code == "TOOL_INPUT_INVALID"

        with pytest.raises(AppError) as forbidden:
            await tool_registry.invoke(
                "inventory.search", {"category": "笔记本电脑"}, techadmin, session
            )
        assert forbidden.value.code == "TOOL_NOT_ALLOWED"
        await session.close()


@pytest.mark.asyncio
async def test_confirmed_intent_creates_exactly_one_draft(client: httpx.AsyncClient) -> None:
    employee = await login(client, "employee")
    created_session = await client.post(
        "/api/v1/chat/sessions", headers=headers(employee), json={"title": "幂等确认"}
    )
    session_id = created_session.json()["id"]
    turn = await client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        headers=headers(employee),
        json={"content": "采购10台笔记本，每台6000元，用于研发办公"},
    )
    assert turn.status_code == 200
    assistant = turn.json()["assistant_message"]
    intent = turn.json()["parse_result"]["intent"]

    first = await client.post(
        f"/api/v1/chat/messages/{assistant['id']}/confirm-intent",
        headers=headers(employee),
        json={"intent": intent},
    )
    assert first.status_code == 200, first.text
    assert first.json()["purchase_request_created"] is True
    request_id = first.json()["purchase_request_id"]

    repeated = await client.post(
        f"/api/v1/chat/messages/{assistant['id']}/confirm-intent",
        headers=headers(employee),
        json={"intent": intent},
    )
    assert repeated.status_code == 200
    assert repeated.json()["purchase_request_created"] is False
    assert repeated.json()["purchase_request_id"] == request_id

    listing = await client.get(
        "/api/v1/procurements?page=1&page_size=100", headers=headers(employee)
    )
    assert sum(item["id"] == request_id for item in listing.json()["items"]) == 1

    changed = {**intent, "quantity": 11, "total_budget": "66000.00"}
    conflict = await client.post(
        f"/api/v1/chat/messages/{assistant['id']}/confirm-intent",
        headers=headers(employee),
        json={"intent": changed},
    )
    assert conflict.status_code == 409
