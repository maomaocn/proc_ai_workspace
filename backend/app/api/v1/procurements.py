import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DatabaseSession
from app.models.procurement import PurchaseRequest
from app.schemas.approval import (
    ApprovalPreview,
    ProcurementStateResponse,
    ProcurementSubmissionResponse,
    ProcurementVersionRequest,
)
from app.schemas.common import Page
from app.schemas.procurement import (
    ProcurementPlanResponse,
    PurchaseRequestCreate,
    PurchaseRequestDetail,
    PurchaseRequestRead,
    PurchaseRequestUpdate,
)
from app.services.approval import approval_service
from app.services.procurement import procurement_service

router = APIRouter(prefix="/procurements", tags=["Procurements"])
IdempotencyKey = Annotated[uuid.UUID, Header(alias="Idempotency-Key")]


@router.get("", response_model=Page[PurchaseRequestRead])
async def list_procurements(
    user: CurrentUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Annotated[str | None, Query(max_length=32)] = None,
    query: Annotated[str | None, Query(max_length=160)] = None,
) -> Page[PurchaseRequestRead]:
    filters = []
    if "ADMIN" not in user.roles:
        filters.append(PurchaseRequest.requester_id == user.id)
    if status:
        filters.append(PurchaseRequest.status == status)
    if query:
        pattern = f"%{query.strip()}%"
        filters.append(
            or_(PurchaseRequest.title.ilike(pattern), PurchaseRequest.category.ilike(pattern))
        )
    total = (
        await session.scalar(select(func.count()).select_from(PurchaseRequest).where(*filters)) or 0
    )
    items = list(
        (
            await session.scalars(
                select(PurchaseRequest)
                .where(*filters)
                .options(selectinload(PurchaseRequest.requester))
                .order_by(PurchaseRequest.updated_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return Page(items=items, page=page, page_size=page_size, total=total)


@router.post("", response_model=PurchaseRequestDetail, status_code=201)
async def create_procurement(
    body: PurchaseRequestCreate, user: CurrentUser, session: DatabaseSession
) -> PurchaseRequestDetail:
    purchase = procurement_service.new_draft(user, body)
    session.add(purchase)
    await session.commit()
    loaded = await procurement_service.get(session, purchase.id)
    return procurement_service.to_detail(loaded)


@router.get("/{request_id}", response_model=PurchaseRequestDetail)
async def get_procurement(
    request_id: uuid.UUID, user: CurrentUser, session: DatabaseSession
) -> PurchaseRequestDetail:
    purchase = await procurement_service.get(session, request_id)
    procurement_service.require_read(purchase, user)
    return procurement_service.to_detail(purchase)


@router.patch("/{request_id}", response_model=PurchaseRequestDetail)
async def update_procurement(
    request_id: uuid.UUID,
    body: PurchaseRequestUpdate,
    user: CurrentUser,
    session: DatabaseSession,
) -> PurchaseRequestDetail:
    purchase = await procurement_service.get(session, request_id, for_update=True)
    procurement_service.require_owner_draft(purchase, user)
    updated = await procurement_service.update_draft(session, purchase, body)
    return procurement_service.to_detail(updated)


@router.post("/{request_id}/plan", response_model=ProcurementPlanResponse)
async def build_procurement_plan(
    request_id: uuid.UUID, user: CurrentUser, session: DatabaseSession
) -> ProcurementPlanResponse:
    purchase = await procurement_service.get(session, request_id, for_update=True)
    return await procurement_service.build_plan(session, purchase, user)


@router.get("/{request_id}/approval-preview", response_model=ApprovalPreview)
async def preview_approval(
    request_id: uuid.UUID, user: CurrentUser, session: DatabaseSession
) -> ApprovalPreview:
    purchase = await procurement_service.get(session, request_id)
    return await approval_service.preview(session, purchase, user)


@router.post("/{request_id}/submit", response_model=ProcurementSubmissionResponse)
async def submit_procurement(
    request_id: uuid.UUID,
    body: ProcurementVersionRequest,
    idempotency_key: IdempotencyKey,
    request: Request,
    user: CurrentUser,
    session: DatabaseSession,
) -> ProcurementSubmissionResponse:
    return await approval_service.submit(
        session,
        request_id,
        body.version,
        idempotency_key,
        user,
        request.state.request_id,
    )


@router.post("/{request_id}/cancel", response_model=ProcurementStateResponse)
async def cancel_procurement(
    request_id: uuid.UUID,
    body: ProcurementVersionRequest,
    idempotency_key: IdempotencyKey,
    request: Request,
    user: CurrentUser,
    session: DatabaseSession,
) -> ProcurementStateResponse:
    return await approval_service.cancel(
        session,
        request_id,
        body.version,
        idempotency_key,
        user,
        request.state.request_id,
    )
