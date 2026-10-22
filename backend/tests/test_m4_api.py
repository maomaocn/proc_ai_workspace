import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import workflow_runtime
from app.core.config import settings
from app.db.seed import DEMO_PASSWORD, seed_demo_data
from app.db.session import SessionFactory, engine, get_session
from app.main import app
from app.models.approval import (
    AgentRun,
    AgentStep,
    ApprovalDecision,
    ApprovalRule,
    ApprovalTask,
    AuditEvent,
    IdempotencyRecord,
    WorkflowResumeEvent,
)
from app.models.procurement import PurchaseCandidate, PurchaseRequest
from app.rag.vector_store import get_vector_store

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS", "false").lower() != "true",
    reason="set RUN_DB_TESTS=true to run PostgreSQL integration tests",
)


@pytest_asyncio.fixture
async def context(tmp_path: Path) -> AsyncIterator[tuple[httpx.AsyncClient, AsyncSession]]:
    await seed_demo_data()
    old_chroma_path = settings.chroma_path
    old_collection_name = settings.chroma_collection_name
    settings.chroma_path = str(tmp_path / "chroma")
    settings.chroma_collection_name = f"test-m4-{uuid.uuid4().hex}"
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

        existing_threads = set(
            (await db_session.scalars(select(AgentRun.graph_thread_id))).all()
        )
        app.dependency_overrides[get_session] = override_session
        created_threads: set[str] = set()
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                yield client, db_session
        finally:
            current_threads = set(
                (await db_session.scalars(select(AgentRun.graph_thread_id))).all()
            )
            created_threads = current_threads - existing_threads
            app.dependency_overrides.clear()
            await db_session.close()
            await transaction.rollback()
            for thread_id in created_threads:
                await workflow_runtime.delete_thread(thread_id)

    get_vector_store.cache_clear()
    settings.chroma_path = old_chroma_path
    settings.chroma_collection_name = old_collection_name


async def login(client: httpx.AsyncClient, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str, key: uuid.UUID | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if key is not None:
        headers["Idempotency-Key"] = str(key)
    return headers


def draft_payload(quantity: int = 10) -> dict[str, object]:
    return {
        "title": f"M4 审批测试 {uuid.uuid4().hex[:8]}",
        "category": "笔记本电脑",
        "item_description": "研发办公笔记本",
        "quantity": quantity,
        "unit_price_limit": "6000.00",
        "purpose": "研发办公",
        "priority": "NORMAL",
        "notes": "M4 自动化测试",
    }


async def create_planned_draft(
    client: httpx.AsyncClient, token: str, *, quantity: int = 10
) -> dict:
    created = await client.post(
        "/api/v1/procurements", headers=auth(token), json=draft_payload(quantity)
    )
    assert created.status_code == 201, created.text
    planned = await client.post(
        f"/api/v1/procurements/{created.json()['id']}/plan", headers=auth(token)
    )
    assert planned.status_code == 200, planned.text
    return planned.json()["procurement"]


async def submit_draft(
    client: httpx.AsyncClient, token: str, draft: dict, key: uuid.UUID | None = None
) -> tuple[dict, uuid.UUID]:
    actual_key = key or uuid.uuid4()
    response = await client.post(
        f"/api/v1/procurements/{draft['id']}/submit",
        headers=auth(token, actual_key),
        json={"version": draft["version"]},
    )
    assert response.status_code == 200, response.text
    return response.json(), actual_key


@pytest.mark.asyncio
async def test_rule_threshold_submission_idempotency_and_checkpoint(
    context: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _ = context
    employee = await login(client, "employee")

    low = await create_planned_draft(client, employee, quantity=1)
    low_preview = await client.get(
        f"/api/v1/procurements/{low['id']}/approval-preview", headers=auth(employee)
    )
    assert low_preview.status_code == 200
    assert len(low_preview.json()["stages"]) == 1
    assert low_preview.json()["stages"][0]["assignee_username"] == "manager"

    high = await create_planned_draft(client, employee, quantity=10)
    high_preview = await client.get(
        f"/api/v1/procurements/{high['id']}/approval-preview", headers=auth(employee)
    )
    assert high_preview.status_code == 200
    assert [item["stage"] for item in high_preview.json()["stages"]] == [1, 2]
    assert [item["assignee_username"] for item in high_preview.json()["stages"]] == [
        "manager",
        "approver",
    ]

    missing_key = await client.post(
        f"/api/v1/procurements/{high['id']}/submit",
        headers=auth(employee),
        json={"version": high["version"]},
    )
    assert missing_key.status_code == 400

    submitted, key = await submit_draft(client, employee, high)
    assert submitted["purchase_status"] == "PENDING_APPROVAL"
    assert [item["status"] for item in submitted["approval_tasks"]] == [
        "PENDING",
        "WAITING",
    ]
    replay = await client.post(
        f"/api/v1/procurements/{high['id']}/submit",
        headers=auth(employee, key),
        json={"version": high["version"]},
    )
    assert replay.status_code == 200
    assert replay.json() == submitted
    conflict = await client.post(
        f"/api/v1/procurements/{high['id']}/submit",
        headers=auth(employee, key),
        json={"version": high["version"] + 1},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

    snapshot = await workflow_runtime.snapshot(submitted["run"]["graph_thread_id"])
    assert snapshot["values"]["status"] == "WAITING_APPROVAL"
    assert snapshot["interrupts"][0]["stage"] == 1


@pytest.mark.asyncio
async def test_unplanned_draft_cannot_submit_and_cancel_is_idempotent(
    context: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _ = context
    employee = await login(client, "employee")
    created = await client.post(
        "/api/v1/procurements",
        headers=auth(employee),
        json=draft_payload(quantity=1),
    )
    assert created.status_code == 201
    draft = created.json()

    invalid_submit = await client.post(
        f"/api/v1/procurements/{draft['id']}/submit",
        headers=auth(employee, uuid.uuid4()),
        json={"version": draft["version"]},
    )
    assert invalid_submit.status_code == 422
    assert invalid_submit.json()["error"]["code"] == "BUSINESS_RULE_VIOLATION"

    cancel_key = uuid.uuid4()
    cancelled = await client.post(
        f"/api/v1/procurements/{draft['id']}/cancel",
        headers=auth(employee, cancel_key),
        json={"version": draft["version"]},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["purchase_status"] == "CANCELLED"
    replay = await client.post(
        f"/api/v1/procurements/{draft['id']}/cancel",
        headers=auth(employee, cancel_key),
        json={"version": draft["version"]},
    )
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True

    edit_after_cancel = await client.patch(
        f"/api/v1/procurements/{draft['id']}",
        headers=auth(employee),
        json={"version": cancelled.json()["version"], "title": "不应允许编辑"},
    )
    assert edit_after_cancel.status_code == 409


@pytest.mark.asyncio
async def test_sequential_approval_resume_and_decision_idempotency(
    context: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _ = context
    employee = await login(client, "employee")
    manager = await login(client, "manager")
    approver = await login(client, "approver")
    draft = await create_planned_draft(client, employee)
    submitted, _ = await submit_draft(client, employee, draft)
    first, second = submitted["approval_tasks"]

    first_key = uuid.uuid4()
    approved_first = await client.post(
        f"/api/v1/approvals/tasks/{first['id']}/decision",
        headers=auth(manager, first_key),
        json={"action": "APPROVE", "comment": "部门预算与用途已核验"},
    )
    assert approved_first.status_code == 200, approved_first.text
    assert approved_first.json()["purchase_status"] == "PENDING_APPROVAL"
    assert approved_first.json()["next_task_id"] == second["id"]

    replay = await client.post(
        f"/api/v1/approvals/tasks/{first['id']}/decision",
        headers=auth(manager, first_key),
        json={"action": "APPROVE", "comment": "部门预算与用途已核验"},
    )
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True
    conflict = await client.post(
        f"/api/v1/approvals/tasks/{first['id']}/decision",
        headers=auth(manager, first_key),
        json={"action": "REJECT", "comment": "相同幂等键不同决定"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

    before_final = await client.get(f"/api/v1/procurements/{draft['id']}", headers=auth(employee))
    assert before_final.json()["status"] == "PENDING_APPROVAL"

    approved_second = await client.post(
        f"/api/v1/approvals/tasks/{second['id']}/decision",
        headers=auth(approver, uuid.uuid4()),
        json={"action": "APPROVE", "comment": "财务预算已复核"},
    )
    assert approved_second.status_code == 200, approved_second.text
    assert approved_second.json()["purchase_status"] == "APPROVED"
    final = await client.get(f"/api/v1/procurements/{draft['id']}", headers=auth(employee))
    assert final.json()["status"] == "APPROVED"
    assert [item["status"] for item in final.json()["approval_tasks"]] == [
        "APPROVED",
        "APPROVED",
    ]
    snapshot = await workflow_runtime.snapshot(submitted["run"]["graph_thread_id"])
    assert snapshot["values"]["status"] == "APPROVED"
    assert snapshot["next"] == []


@pytest.mark.asyncio
async def test_rejection_reason_permissions_and_self_approval(
    context: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, _ = context
    employee = await login(client, "employee")
    manager = await login(client, "manager")
    approver = await login(client, "approver")
    techadmin = await login(client, "techadmin")

    draft = await create_planned_draft(client, employee)
    submitted, _ = await submit_draft(client, employee, draft)
    first, second = submitted["approval_tasks"]
    tech_denied = await client.post(
        f"/api/v1/approvals/tasks/{first['id']}/decision",
        headers=auth(techadmin, uuid.uuid4()),
        json={"action": "APPROVE"},
    )
    assert tech_denied.status_code == 403
    wrong_assignee = await client.post(
        f"/api/v1/approvals/tasks/{first['id']}/decision",
        headers=auth(approver, uuid.uuid4()),
        json={"action": "APPROVE"},
    )
    assert wrong_assignee.status_code == 403
    invalid_reason = await client.post(
        f"/api/v1/approvals/tasks/{first['id']}/decision",
        headers=auth(manager, uuid.uuid4()),
        json={"action": "REJECT", "comment": "短"},
    )
    assert invalid_reason.status_code == 400

    rejected = await client.post(
        f"/api/v1/approvals/tasks/{first['id']}/decision",
        headers=auth(manager, uuid.uuid4()),
        json={"action": "REJECT", "comment": "预算依据不足，请补充说明"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["purchase_status"] == "REJECTED"
    detail = await client.get(f"/api/v1/procurements/{draft['id']}", headers=auth(employee))
    assert [item["status"] for item in detail.json()["approval_tasks"]] == [
        "REJECTED",
        "SKIPPED",
    ]
    assert detail.json()["audit_events"][-1]["action"] == "APPROVAL_REJECT"

    own_draft = await create_planned_draft(client, manager)
    own_submission, _ = await submit_draft(client, manager, own_draft)
    own_task = own_submission["approval_tasks"][0]
    self_review = await client.post(
        f"/api/v1/approvals/tasks/{own_task['id']}/decision",
        headers=auth(manager, uuid.uuid4()),
        json={"action": "APPROVE"},
    )
    assert self_review.status_code == 403
    assert self_review.json()["error"]["code"] == "SELF_APPROVAL_FORBIDDEN"


@pytest.mark.asyncio
async def test_rule_management_conflict_and_missing_rule(
    context: tuple[httpx.AsyncClient, AsyncSession],
) -> None:
    client, session = context
    admin = await login(client, "admin")
    employee = await login(client, "employee")
    techadmin = await login(client, "techadmin")

    rules = await client.get("/api/v1/admin/approval-rules", headers=auth(admin))
    assert rules.status_code == 200
    assert len(rules.json()) >= 3
    denied = await client.get("/api/v1/admin/approval-rules", headers=auth(techadmin))
    assert denied.status_code == 403
    overlap = await client.post(
        "/api/v1/admin/approval-rules",
        headers=auth(admin),
        json={
            "min_amount": "5000.00",
            "max_amount": "15000.00",
            "stage": 1,
            "approver_role": "APPROVER",
            "active": True,
        },
    )
    assert overlap.status_code == 409
    assert overlap.json()["error"]["code"] == "RULE_RANGE_CONFLICT"

    await session.execute(update(ApprovalRule).values(active=False))
    await session.flush()
    draft = await create_planned_draft(client, employee, quantity=1)
    preview = await client.get(
        f"/api/v1/procurements/{draft['id']}/approval-preview", headers=auth(employee)
    )
    assert preview.status_code == 422
    assert preview.json()["error"]["code"] == "RULE_CONFIGURATION_MISSING"


@pytest.mark.asyncio
async def test_concurrent_decisions_create_only_one_immutable_record() -> None:
    await seed_demo_data()
    app.dependency_overrides.clear()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        employee = await login(client, "employee")
        manager = await login(client, "manager")
        draft = await create_planned_draft(client, employee)
        submitted, _ = await submit_draft(client, employee, draft)
        task_id = submitted["approval_tasks"][0]["id"]
        thread_id = submitted["run"]["graph_thread_id"]

        async def decide(action: str, comment: str) -> httpx.Response:
            return await client.post(
                f"/api/v1/approvals/tasks/{task_id}/decision",
                headers=auth(manager, uuid.uuid4()),
                json={"action": action, "comment": comment},
            )

        responses = await asyncio.gather(
            decide("APPROVE", "并发批准请求"),
            decide("REJECT", "并发驳回请求"),
        )
        assert sorted(item.status_code for item in responses) == [200, 409]

    request_id = uuid.UUID(draft["id"])
    async with SessionFactory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(ApprovalDecision)
            .join(ApprovalTask, ApprovalTask.id == ApprovalDecision.task_id)
            .where(ApprovalTask.request_id == request_id)
        )
        assert count == 1
        run_ids = list(
            (
                await session.scalars(select(AgentRun.id).where(AgentRun.request_id == request_id))
            ).all()
        )
        task_ids = list(
            (
                await session.scalars(
                    select(ApprovalTask.id).where(ApprovalTask.request_id == request_id)
                )
            ).all()
        )
        await session.execute(
            delete(WorkflowResumeEvent).where(WorkflowResumeEvent.run_id.in_(run_ids))
        )
        await session.execute(
            delete(ApprovalDecision).where(ApprovalDecision.task_id.in_(task_ids))
        )
        await session.execute(delete(AgentStep).where(AgentStep.run_id.in_(run_ids)))
        await session.execute(delete(ApprovalTask).where(ApprovalTask.request_id == request_id))
        await session.execute(delete(AgentRun).where(AgentRun.request_id == request_id))
        await session.execute(
            delete(IdempotencyRecord).where(
                IdempotencyRecord.resource_type == "PURCHASE_REQUEST",
                IdempotencyRecord.resource_id == request_id,
            )
        )
        await session.execute(
            delete(AuditEvent).where(
                AuditEvent.resource_type == "PURCHASE_REQUEST",
                AuditEvent.resource_id == request_id,
            )
        )
        await session.execute(
            delete(PurchaseCandidate).where(PurchaseCandidate.request_id == request_id)
        )
        await session.execute(delete(PurchaseRequest).where(PurchaseRequest.id == request_id))
        await session.commit()
    await workflow_runtime.delete_thread(thread_id)
