import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DatabaseSession, require_roles
from app.models.approval import ApprovalDecision, ApprovalTask
from app.models.identity import User
from app.models.procurement import PurchaseRequest
from app.schemas.approval import (
    ApprovalDecisionCreate,
    ApprovalDecisionResponse,
    ApprovalInboxItem,
    ApprovalRuleCreate,
    ApprovalRuleRead,
    ApprovalRuleUpdate,
    ApprovalTaskDetail,
    ApprovalTaskRead,
)
from app.schemas.common import Page
from app.services.approval import approval_service

router = APIRouter(prefix="/approvals", tags=["Approvals"])
rules_router = APIRouter(prefix="/admin/approval-rules", tags=["Approval Rules"])
ApproverUser = Annotated[User, Depends(require_roles("APPROVER"))]
AdminUser = Annotated[User, Depends(require_roles("ADMIN"))]
IdempotencyKey = Annotated[uuid.UUID, Header(alias="Idempotency-Key")]


@router.get("/tasks", response_model=Page[ApprovalInboxItem])
async def list_tasks(
    actor: ApproverUser,
    session: DatabaseSession,
    view: Literal["pending", "processed", "all"] = "pending",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[ApprovalInboxItem]:
    filters = [ApprovalTask.assignee_id == actor.id]
    if view == "pending":
        filters.append(ApprovalTask.status == "PENDING")
    elif view == "processed":
        filters.append(ApprovalTask.status.in_(("APPROVED", "REJECTED")))
    total = (
        await session.scalar(select(func.count()).select_from(ApprovalTask).where(*filters)) or 0
    )
    tasks = list(
        (
            await session.scalars(
                select(ApprovalTask)
                .where(*filters)
                .options(
                    selectinload(ApprovalTask.assignee),
                    selectinload(ApprovalTask.decisions).selectinload(ApprovalDecision.actor),
                    selectinload(ApprovalTask.request).selectinload(PurchaseRequest.requester),
                )
                .order_by(ApprovalTask.updated_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .unique()
        .all()
    )
    return Page(
        items=[
            ApprovalInboxItem(
                task=ApprovalTaskRead.model_validate(task),
                request_title=task.request.title,
                requester_username=task.request.requester.username,
                total_budget=task.request.total_budget,
                purchase_status=task.request.status,
                submitted_at=task.created_at,
            )
            for task in tasks
        ],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/tasks/{task_id}", response_model=ApprovalTaskDetail)
async def get_task(
    task_id: uuid.UUID, actor: ApproverUser, session: DatabaseSession
) -> ApprovalTaskDetail:
    return await approval_service.task_detail(session, task_id, actor)


@router.post("/tasks/{task_id}/decision", response_model=ApprovalDecisionResponse)
async def decide_task(
    task_id: uuid.UUID,
    body: ApprovalDecisionCreate,
    idempotency_key: IdempotencyKey,
    request: Request,
    actor: ApproverUser,
    session: DatabaseSession,
) -> ApprovalDecisionResponse:
    return await approval_service.decide(
        session,
        task_id,
        body,
        idempotency_key,
        actor,
        request.state.request_id,
    )


@rules_router.get("", response_model=list[ApprovalRuleRead])
async def list_rules(_: AdminUser, session: DatabaseSession) -> list[ApprovalRuleRead]:
    return await approval_service.list_rules(session)


@rules_router.post("", response_model=ApprovalRuleRead, status_code=201)
async def create_rule(
    body: ApprovalRuleCreate, _: AdminUser, session: DatabaseSession
) -> ApprovalRuleRead:
    return await approval_service.create_rule(session, body)


@rules_router.patch("/{rule_id}", response_model=ApprovalRuleRead)
async def update_rule(
    rule_id: uuid.UUID,
    body: ApprovalRuleUpdate,
    _: AdminUser,
    session: DatabaseSession,
) -> ApprovalRuleRead:
    return await approval_service.update_rule(session, rule_id, body)
