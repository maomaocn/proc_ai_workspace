import uuid
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.models.approval import AgentRun, ApprovalDecision, ApprovalTask, AuditEvent
from app.models.identity import User
from app.models.procurement import PurchaseCandidate, PurchaseRequest, SupplierQuote
from app.schemas.chat import PurchaseIntent
from app.schemas.knowledge import SearchResponse
from app.schemas.procurement import (
    ProcurementPlanResponse,
    PurchaseCandidateRead,
    PurchaseRequestCreate,
    PurchaseRequestDetail,
    PurchaseRequestUpdate,
    ToolCallRead,
)
from app.tools.registry import ToolExecution, tool_registry

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT)


def total_price(quantity: int, unit_price: Decimal) -> Decimal:
    return money(unit_price * quantity)


class ProcurementService:
    async def get(
        self,
        session: AsyncSession,
        request_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> PurchaseRequest:
        query = (
            select(PurchaseRequest)
            .where(PurchaseRequest.id == request_id)
            .execution_options(populate_existing=True)
            .options(
                selectinload(PurchaseRequest.requester),
                selectinload(PurchaseRequest.candidates).selectinload(PurchaseCandidate.item),
                selectinload(PurchaseRequest.candidates).selectinload(PurchaseCandidate.supplier),
                selectinload(PurchaseRequest.candidates)
                .selectinload(PurchaseCandidate.source_quote)
                .selectinload(SupplierQuote.supplier),
                selectinload(PurchaseRequest.candidates)
                .selectinload(PurchaseCandidate.source_quote)
                .selectinload(SupplierQuote.inventory_item),
                selectinload(PurchaseRequest.approval_tasks).selectinload(ApprovalTask.assignee),
                selectinload(PurchaseRequest.approval_tasks)
                .selectinload(ApprovalTask.decisions)
                .selectinload(ApprovalDecision.actor),
                selectinload(PurchaseRequest.workflow_runs).selectinload(AgentRun.steps),
            )
        )
        if for_update:
            query = query.with_for_update()
        purchase = await session.scalar(query)
        if purchase is None:
            raise AppError(404, "NOT_FOUND", "采购申请不存在")
        purchase._audit_events = list(
            (
                await session.scalars(
                    select(AuditEvent)
                    .where(
                        AuditEvent.resource_type == "PURCHASE_REQUEST",
                        AuditEvent.resource_id == request_id,
                    )
                    .order_by(AuditEvent.created_at)
                )
            ).all()
        )
        return purchase

    def require_read(self, purchase: PurchaseRequest, user: User) -> None:
        if purchase.requester_id != user.id and "ADMIN" not in user.roles:
            raise AppError(403, "FORBIDDEN", "无权查看此采购申请")

    def require_owner_draft(self, purchase: PurchaseRequest, user: User) -> None:
        if purchase.requester_id != user.id:
            raise AppError(403, "FORBIDDEN", "只有申请人可修改自己的采购草稿")
        if purchase.status != "DRAFT":
            raise AppError(409, "STATE_CONFLICT", "只有草稿状态可以修改或生成方案")

    def new_draft(
        self,
        user: User,
        body: PurchaseRequestCreate,
        *,
        linked_run_id: uuid.UUID | None = None,
    ) -> PurchaseRequest:
        if body.total_budget is None:
            raise AppError(422, "BUSINESS_RULE_VIOLATION", "无法确定采购总预算")
        return PurchaseRequest(
            requester_id=user.id,
            title=body.title,
            category=body.category,
            item_description=body.item_description,
            quantity=body.quantity,
            unit_price_limit=money(body.unit_price_limit),
            total_budget=money(body.total_budget),
            purpose=body.purpose,
            priority=body.priority,
            notes=body.notes,
            status="DRAFT",
            version=0,
            linked_run_id=linked_run_id,
        )

    def from_confirmed_intent(
        self,
        user: User,
        intent: PurchaseIntent,
        linked_run_id: uuid.UUID | None,
    ) -> PurchaseRequest:
        if not all(
            (
                intent.category,
                intent.item_description,
                intent.quantity,
                intent.unit_price_limit,
                intent.purpose,
            )
        ):
            raise AppError(422, "BUSINESS_RULE_VIOLATION", "采购意图缺少必填字段")
        body = PurchaseRequestCreate(
            title=f"{intent.category}采购",
            category=intent.category,
            item_description=intent.item_description,
            quantity=intent.quantity,
            unit_price_limit=intent.unit_price_limit,
            total_budget=intent.total_budget,
            purpose=intent.purpose,
            priority=intent.priority,
            notes=intent.notes,
        )
        return self.new_draft(user, body, linked_run_id=linked_run_id)

    async def update_draft(
        self,
        session: AsyncSession,
        purchase: PurchaseRequest,
        body: PurchaseRequestUpdate,
    ) -> PurchaseRequest:
        if purchase.version != body.version:
            raise AppError(
                409,
                "STATE_CONFLICT",
                "采购草稿已被更新，请刷新后重试",
                {"current_version": purchase.version},
            )
        values = body.model_dump(exclude_unset=True, exclude={"version", "total_budget"})
        proposed_quantity = body.quantity if body.quantity is not None else purchase.quantity
        proposed_unit_price = (
            body.unit_price_limit
            if body.unit_price_limit is not None
            else purchase.unit_price_limit
        )
        expected = total_price(proposed_quantity, proposed_unit_price)
        if body.total_budget is not None and money(body.total_budget) != expected:
            raise AppError(
                422,
                "BUSINESS_RULE_VIOLATION",
                "总预算必须等于数量乘以单价上限",
                {"expected_total_budget": str(expected)},
            )
        for field, value in values.items():
            setattr(purchase, field, value)
        purchase.total_budget = expected
        purchase.version += 1
        await session.execute(
            delete(PurchaseCandidate).where(PurchaseCandidate.request_id == purchase.id)
        )
        await session.commit()
        return await self.get(session, purchase.id)

    async def build_plan(
        self,
        session: AsyncSession,
        purchase: PurchaseRequest,
        user: User,
    ) -> ProcurementPlanResponse:
        self.require_owner_draft(purchase, user)
        executions: list[ToolExecution] = []
        inventory = await tool_registry.invoke(
            "inventory.search",
            {"category": purchase.category, "min_qty": 0, "limit": 10},
            user,
            session,
        )
        executions.append(inventory)

        policy = await tool_registry.invoke(
            "policy.search",
            {"query": f"{purchase.category} 采购预算与审批要求", "top_k": 3},
            user,
            session,
        )
        executions.append(policy)

        await session.execute(
            delete(PurchaseCandidate).where(PurchaseCandidate.request_id == purchase.id)
        )
        for item in inventory.output.get("items", []):
            quote_result = await tool_registry.invoke(
                "supplier.quote",
                {"item_id": item["id"], "quantity": purchase.quantity, "limit": 10},
                user,
                session,
            )
            executions.append(quote_result)
            for quote in quote_result.output.get("quotes", []):
                session.add(
                    PurchaseCandidate(
                        request_id=purchase.id,
                        item_id=uuid.UUID(quote["item_id"]),
                        supplier_id=uuid.UUID(quote["supplier_id"]),
                        quantity=purchase.quantity,
                        unit_price=Decimal(quote["unit_price"]),
                        total_price=Decimal(quote["total_price"]),
                        source_quote_id=uuid.UUID(quote["quote_id"]),
                    )
                )
        await session.commit()
        refreshed = await self.get(session, purchase.id)
        policy_payload = dict(policy.output)
        policy_payload.pop("tool_source", None)
        return ProcurementPlanResponse(
            procurement=self.to_detail(refreshed),
            policy=SearchResponse.model_validate(policy_payload),
            tool_calls=[self._tool_call(item) for item in executions],
        )

    def to_detail(self, purchase: PurchaseRequest) -> PurchaseRequestDetail:
        payload = {
            "id": purchase.id,
            "requester_id": purchase.requester_id,
            "requester": purchase.requester,
            "title": purchase.title,
            "category": purchase.category,
            "item_description": purchase.item_description,
            "quantity": purchase.quantity,
            "unit_price_limit": purchase.unit_price_limit,
            "total_budget": purchase.total_budget,
            "purpose": purchase.purpose,
            "priority": purchase.priority,
            "notes": purchase.notes,
            "status": purchase.status,
            "version": purchase.version,
            "linked_run_id": purchase.linked_run_id,
            "created_at": purchase.created_at,
            "updated_at": purchase.updated_at,
            "candidates": [self._candidate(item, purchase) for item in purchase.candidates],
            "approval_tasks": purchase.approval_tasks,
            "workflow_run": purchase.workflow_runs[-1] if purchase.workflow_runs else None,
            "audit_events": getattr(purchase, "_audit_events", []),
        }
        return PurchaseRequestDetail.model_validate(payload)

    def _candidate(
        self, candidate: PurchaseCandidate, purchase: PurchaseRequest
    ) -> PurchaseCandidateRead:
        return PurchaseCandidateRead.model_validate(
            {
                "id": candidate.id,
                "request_id": candidate.request_id,
                "item_id": candidate.item_id,
                "supplier_id": candidate.supplier_id,
                "quantity": candidate.quantity,
                "unit_price": candidate.unit_price,
                "total_price": candidate.total_price,
                "source_quote_id": candidate.source_quote_id,
                "item": candidate.item,
                "supplier": candidate.supplier,
                "source_quote": candidate.source_quote,
                "stock_sufficient": candidate.item.available_qty >= candidate.quantity,
                "within_unit_limit": candidate.unit_price <= purchase.unit_price_limit,
                "within_total_budget": candidate.total_price <= purchase.total_budget,
            }
        )

    def _tool_call(self, execution: ToolExecution) -> ToolCallRead:
        return ToolCallRead(
            name=execution.name,
            duration_ms=execution.duration_ms,
            source=execution.source,
            item_count=execution.item_count,
        )


procurement_service = ProcurementService()
