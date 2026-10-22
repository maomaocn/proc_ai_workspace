from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.mcp.client import mcp_client
from app.models.identity import User
from app.rag.permissions import accessible_collection_query, require_collection_permission
from app.rag.service import knowledge_service
from app.tools.read_service import query_inventory, query_supplier_quotes
from app.tools.schemas import (
    InventorySearchInput,
    PolicySearchInput,
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
    source: str = "LOCAL"
    external_name: str | None = None
    timeout_ms: int = 5000
    max_calls_per_run: int = 4


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
            raise RuntimeError("M5 Tool Registry accepts read-only tools only")
        self._tools[definition.name] = definition

    def get(self, name: str) -> ToolDefinition:
        definition = self._tools.get(name)
        if definition is None:
            raise AppError(404, "TOOL_NOT_FOUND", "工具不存在")
        return definition

    def definitions(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def schema(self, name: str) -> dict[str, Any]:
        definition = self.get(name)
        return definition.input_model.model_json_schema()

    async def invoke(
        self,
        name: str,
        payload: dict[str, Any],
        user: User,
        session: AsyncSession,
    ) -> ToolExecution:
        definition = self.get(name)
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
            async with asyncio.timeout(definition.timeout_ms / 1000):
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
    return await query_inventory(session, InventorySearchInput.model_validate(parameters))


async def _supplier_quote(session: AsyncSession, _: User, parameters: BaseModel) -> dict[str, Any]:
    return await query_supplier_quotes(session, SupplierQuoteInput.model_validate(parameters))


async def _mcp_inventory_search(_: AsyncSession, __: User, parameters: BaseModel) -> dict[str, Any]:
    request = InventorySearchInput.model_validate(parameters)
    return await mcp_client.call("inventory_search", request.model_dump(mode="json"))


async def _mcp_supplier_quote(_: AsyncSession, __: User, parameters: BaseModel) -> dict[str, Any]:
    request = SupplierQuoteInput.model_validate(parameters)
    return await mcp_client.call("supplier_quote", request.model_dump(mode="json"))


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
_MCP_ROLES = frozenset({"EMPLOYEE", "APPROVER", "PROCUREMENT", "ADMIN", "TECH_ADMIN"})
tool_registry.register(
    ToolDefinition(
        name="inventory.search",
        description="查询本地演示库存中的可用商品",
        input_model=InventorySearchInput,
        allowed_roles=_BUSINESS_ROLES,
        executor=_inventory_search,
        timeout_ms=round(settings.tool_timeout_seconds * 1000),
    )
)
tool_registry.register(
    ToolDefinition(
        name="supplier.quote",
        description="查询本地数据库中的演示供应商报价",
        input_model=SupplierQuoteInput,
        allowed_roles=_BUSINESS_ROLES,
        executor=_supplier_quote,
        timeout_ms=round(settings.tool_timeout_seconds * 1000),
    )
)
tool_registry.register(
    ToolDefinition(
        name="policy.search",
        description="在用户获授权的企业制度知识库中检索依据",
        input_model=PolicySearchInput,
        allowed_roles=_BUSINESS_ROLES,
        executor=_policy_search,
        timeout_ms=round(settings.tool_timeout_seconds * 1000),
    )
)
tool_registry.register(
    ToolDefinition(
        name="mcp.inventory.search",
        description="经本地 stdio MCP Server 查询演示库存",
        input_model=InventorySearchInput,
        allowed_roles=_MCP_ROLES,
        executor=_mcp_inventory_search,
        source="MCP",
        external_name="inventory_search",
        timeout_ms=round(settings.tool_timeout_seconds * 1000),
    )
)
tool_registry.register(
    ToolDefinition(
        name="mcp.supplier.quote",
        description="经本地 stdio MCP Server 查询演示供应商报价",
        input_model=SupplierQuoteInput,
        allowed_roles=_MCP_ROLES,
        executor=_mcp_supplier_quote,
        source="MCP",
        external_name="supplier_quote",
        timeout_ms=round(settings.tool_timeout_seconds * 1000),
    )
)
