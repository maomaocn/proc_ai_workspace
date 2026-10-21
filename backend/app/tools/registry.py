from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import AppError
from app.models.identity import User
from app.models.procurement import InventoryItem, SupplierQuote
from app.rag.permissions import accessible_collection_query, require_collection_permission
from app.rag.service import knowledge_service
from app.tools.schemas import (
    InventorySearchInput,
    InventoryToolItem,
    PolicySearchInput,
    QuoteToolItem,
    SupplierQuoteInput,
)

ToolExecutor = Callable[[AsyncSession, User, BaseModel], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_model: type[BaseModel]
    allowed_roles: frozenset[str]
    executor: ToolExecutor
    side_effect: bool = False


@dataclass(frozen=True)
class ToolExecution:
    name: str
    duration_ms: int
    source: str
    output: dict[str, Any]

    @property
    def item_count(self) -> int:
        items = self.output.get("items") or self.output.get("quotes") or self.output.get("hits")
        return len(items) if isinstance(items, list) else 0


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            raise RuntimeError(f"duplicate tool registration: {definition.name}")
        if definition.side_effect:
            raise RuntimeError("M3 Tool Registry accepts read-only tools only")
        self._tools[definition.name] = definition

    def schema(self, name: str) -> dict[str, Any]:
        definition = self._tools.get(name)
        if definition is None:
            raise AppError(404, "TOOL_NOT_FOUND", "工具不存在")
        return definition.input_model.model_json_schema()

    async def invoke(
        self,
        name: str,
        payload: dict[str, Any],
        user: User,
        session: AsyncSession,
    ) -> ToolExecution:
        definition = self._tools.get(name)
        if definition is None:
            raise AppError(404, "TOOL_NOT_FOUND", "工具不存在")
        if user.roles.isdisjoint(definition.allowed_roles):
            raise AppError(403, "TOOL_NOT_ALLOWED", "当前角色无权调用此工具")
        try:
            parameters = definition.input_model.model_validate(payload)
        except ValidationError as exc:
            raise AppError(
                400,
                "TOOL_INPUT_INVALID",
                "工具参数不符合 Schema",
                {"fields": exc.errors(include_input=False, include_context=False)},
            ) from exc

        started = time.perf_counter()
        try:
            async with asyncio.timeout(settings.tool_timeout_seconds):
                output = await definition.executor(session, user, parameters)
        except TimeoutError as exc:
            raise AppError(503, "TOOL_TIMEOUT", "工具执行超时") from exc
        return ToolExecution(
            name=name,
            duration_ms=max(0, round((time.perf_counter() - started) * 1000)),
            source=str(output.get("tool_source", output.get("source", "DATABASE"))),
            output=output,
        )


async def _inventory_search(
    session: AsyncSession, _: User, parameters: BaseModel
) -> dict[str, Any]:
    request = InventorySearchInput.model_validate(parameters)
    limit = min(request.limit, settings.tool_max_result_items)
    rows = list(
        (
            await session.scalars(
                select(InventoryItem)
                .where(
                    InventoryItem.active.is_(True),
                    InventoryItem.category.ilike(f"%{request.category}%"),
                    InventoryItem.available_qty >= request.min_qty,
                )
                .order_by(InventoryItem.reference_price, InventoryItem.sku)
                .limit(limit)
            )
        ).all()
    )
    return {
        "source": "DATABASE",
        "items": [
            InventoryToolItem.model_validate(row, from_attributes=True).model_dump(mode="json")
            for row in rows
        ],
    }


async def _supplier_quote(
    session: AsyncSession, _: User, parameters: BaseModel
) -> dict[str, Any]:
    request = SupplierQuoteInput.model_validate(parameters)
    limit = min(request.limit, settings.tool_max_result_items)
    rows = list(
        (
            await session.scalars(
                select(SupplierQuote)
                .where(SupplierQuote.inventory_item_id == request.item_id)
                .options(
                    selectinload(SupplierQuote.supplier),
                    selectinload(SupplierQuote.inventory_item),
                )
                .order_by(SupplierQuote.unit_price, SupplierQuote.quoted_at.desc())
                .limit(limit)
            )
        ).all()
    )
    quotes: list[dict[str, Any]] = []
    for row in rows:
        if not row.supplier.active or not row.inventory_item.active:
            continue
        total = (row.unit_price * request.quantity).quantize(Decimal("0.01"))
        quotes.append(
            QuoteToolItem(
                quote_id=row.id,
                supplier_id=row.supplier_id,
                supplier_name=row.supplier.name,
                item_id=row.inventory_item_id,
                item_model=row.inventory_item.model,
                available_qty=row.inventory_item.available_qty,
                unit_price=row.unit_price,
                quantity=request.quantity,
                total_price=total,
                currency=row.currency,
                quoted_at=row.quoted_at.isoformat(),
                source_type=row.source_type,
            ).model_dump(mode="json")
        )
    return {"source": "DATABASE", "quotes": quotes}


async def _policy_search(
    session: AsyncSession, user: User, parameters: BaseModel
) -> dict[str, Any]:
    request = PolicySearchInput.model_validate(parameters)
    collection_id = request.collection_id
    if collection_id is None:
        collections = list((await session.scalars(accessible_collection_query(user))).all())
        preferred = next(
            (item for item in collections if item.name == "企业采购制度"),
            collections[0] if collections else None,
        )
        if preferred is None:
            return {
                "source": "MOCK",
                "tool_source": "MOCK_RAG",
                "hits": [],
                "answer": "当前知识库未检索到足够依据。",
                "has_sufficient_evidence": False,
            }
        collection_id = preferred.id
    await require_collection_permission(session, user, collection_id, "READ")
    result = await knowledge_service.search(session, collection_id, request.query, request.top_k)
    payload = result.model_dump(mode="json")
    payload["tool_source"] = "MOCK_RAG"
    return payload


tool_registry = ToolRegistry()
_BUSINESS_ROLES = frozenset({"EMPLOYEE", "APPROVER", "PROCUREMENT", "ADMIN"})
tool_registry.register(
    ToolDefinition(
        name="inventory.search",
        description="查询本地演示库存中的可用商品",
        input_model=InventorySearchInput,
        allowed_roles=_BUSINESS_ROLES,
        executor=_inventory_search,
    )
)
tool_registry.register(
    ToolDefinition(
        name="supplier.quote",
        description="查询本地数据库中的演示供应商报价",
        input_model=SupplierQuoteInput,
        allowed_roles=_BUSINESS_ROLES,
        executor=_supplier_quote,
    )
)
tool_registry.register(
    ToolDefinition(
        name="policy.search",
        description="在用户获授权的企业制度知识库中检索依据",
        input_model=PolicySearchInput,
        allowed_roles=_BUSINESS_ROLES,
        executor=_policy_search,
    )
)
