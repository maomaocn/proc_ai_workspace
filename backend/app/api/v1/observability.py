from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DatabaseSession, require_roles
from app.core.errors import AppError
from app.harness import AgentCall, agent_runner
from app.mcp.client import mcp_client
from app.models.approval import AgentEvent, AgentRun, AgentStep, MCPServerRecord, ToolPolicy
from app.models.identity import User
from app.schemas.common import Page
from app.schemas.observability import (
    AgentRunDetail,
    AgentStepRead,
    MCPServerRead,
    MCPToolRead,
    MCPToolTestRequest,
    MCPToolTestResponse,
    RunSummary,
    WorkflowEdge,
    WorkflowRunDetail,
)
from app.tools.registry import tool_registry

router = APIRouter(tags=["Agent Observability"])
mcp_router = APIRouter(prefix="/mcp", tags=["MCP"])
TechnicalUser = Annotated[User, Depends(require_roles("TECH_ADMIN", "ADMIN"))]


def _duration_ms(run: AgentRun) -> int | None:
    if run.finished_at is None:
        return None
    return max(0, round((run.finished_at - run.started_at).total_seconds() * 1000))


def _run_summary(run: AgentRun) -> RunSummary:
    return RunSummary(
        id=run.id,
        user_id=run.user_id,
        username=run.user.username,
        request_id=run.request_id,
        graph_thread_id=run.graph_thread_id,
        run_type=run.run_type,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_ms=_duration_ms(run),
        error_code=run.error_code,
        model_provider=run.model_provider,
        max_steps=run.max_steps,
        total_timeout_ms=run.total_timeout_ms,
        step_count=max(run.step_count, len(run.steps)),
        tool_call_count=run.tool_call_count,
        retry_count=run.retry_count,
    )


def _step_read(step: AgentStep) -> AgentStepRead:
    return AgentStepRead(
        id=step.id,
        run_id=step.run_id,
        step_index=step.step_index,
        node_name=step.node_name,
        tool_name=step.tool_name,
        status=step.status,
        duration_ms=step.duration_ms,
        input_summary=step.input_summary,
        output_summary=step.output_summary,
        error_code=step.error_code,
        started_at=step.started_at,
        finished_at=step.finished_at,
    )


async def _get_run(session: DatabaseSession, run_id: uuid.UUID) -> AgentRun:
    run = await session.scalar(
        select(AgentRun)
        .where(AgentRun.id == run_id)
        .options(
            selectinload(AgentRun.user),
            selectinload(AgentRun.request),
            selectinload(AgentRun.steps),
        )
    )
    if run is None:
        raise AppError(404, "RUN_NOT_FOUND", "运行记录不存在")
    return run


def _require_run_read(run: AgentRun, user: User) -> None:
    if run.user_id != user.id and user.roles.isdisjoint({"TECH_ADMIN", "ADMIN"}):
        raise AppError(403, "FORBIDDEN", "无权查看此运行")


@router.get("/agent-runs", response_model=Page[RunSummary])
async def list_agent_runs(
    _: TechnicalUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Annotated[str | None, Query(max_length=32)] = None,
    run_type: Annotated[str | None, Query(max_length=24)] = None,
) -> Page[RunSummary]:
    filters = []
    if status:
        filters.append(AgentRun.status == status)
    if run_type:
        filters.append(AgentRun.run_type == run_type)
    total = await session.scalar(select(func.count()).select_from(AgentRun).where(*filters)) or 0
    runs = list(
        (
            await session.scalars(
                select(AgentRun)
                .where(*filters)
                .options(selectinload(AgentRun.user), selectinload(AgentRun.steps))
                .order_by(AgentRun.started_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return Page(
        items=[_run_summary(run) for run in runs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/agent-runs/{run_id}", response_model=AgentRunDetail)
async def get_agent_run(
    run_id: uuid.UUID, user: CurrentUser, session: DatabaseSession
) -> AgentRunDetail:
    run = await _get_run(session, run_id)
    _require_run_read(run, user)
    return AgentRunDetail(
        **_run_summary(run).model_dump(), steps=[_step_read(step) for step in run.steps]
    )


@router.get("/agent-runs/{run_id}/steps", response_model=list[AgentStepRead])
async def get_agent_steps(
    run_id: uuid.UUID, _: TechnicalUser, session: DatabaseSession
) -> list[AgentStepRead]:
    run = await _get_run(session, run_id)
    return [_step_read(step) for step in run.steps]


@router.get("/agent-runs/{run_id}/events")
async def stream_agent_events(
    run_id: uuid.UUID,
    user: CurrentUser,
    session: DatabaseSession,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    # These persisted events are replayable observability output. They are distinct from LangGraph
    # checkpoints, which contain executable workflow position and are accessed by WorkflowRuntime.
    run = await _get_run(session, run_id)
    _require_run_read(run, user)
    try:
        after_seq = int(last_event_id or 0)
    except ValueError as exc:
        raise AppError(400, "LAST_EVENT_ID_INVALID", "Last-Event-ID 必须是整数") from exc
    events = list(
        (
            await session.scalars(
                select(AgentEvent)
                .where(AgentEvent.run_id == run_id, AgentEvent.seq > after_seq)
                .order_by(AgentEvent.seq)
            )
        ).all()
    )

    async def generate() -> AsyncIterator[str]:
        for event in events:
            payload = json.dumps(event.data_json, ensure_ascii=False, default=str)
            yield f"id: {event.seq}\nevent: {event.event_type}\ndata: {payload}\n\n"
        if not events:
            heartbeat = {
                "run_id": str(run_id),
                "seq": after_seq,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            yield f"event: heartbeat\ndata: {json.dumps(heartbeat)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/workflows/runs/{run_id}", response_model=WorkflowRunDetail)
async def get_workflow_run(
    run_id: uuid.UUID, _: TechnicalUser, session: DatabaseSession
) -> WorkflowRunDetail:
    run = await _get_run(session, run_id)
    if run.run_type != "WORKFLOW":
        raise AppError(404, "WORKFLOW_RUN_NOT_FOUND", "工作流运行不存在")
    nodes = [_step_read(step) for step in run.steps]
    edges = [
        WorkflowEdge(source=str(left.id), target=str(right.id))
        for left, right in zip(run.steps, run.steps[1:], strict=False)
    ]
    return WorkflowRunDetail(
        run=_run_summary(run),
        business_number=run.request.title if run.request is not None else None,
        nodes=nodes,
        edges=edges,
    )


@mcp_router.get("/servers", response_model=list[MCPServerRead])
async def list_mcp_servers(_: TechnicalUser, session: DatabaseSession) -> list[MCPServerRead]:
    records = list(
        (await session.scalars(select(MCPServerRecord).order_by(MCPServerRecord.name))).all()
    )
    result: list[MCPServerRead] = []
    for record in records:
        version: str | None = None
        error_code: str | None = None
        tool_count = 0
        try:
            _, version, tools = await mcp_client.discover()
            tool_count = len(tools)
            record.health_status = "HEALTHY"
        except AppError as error:
            record.health_status = "UNHEALTHY"
            error_code = error.code
        record.last_checked_at = datetime.now(UTC)
        result.append(
            MCPServerRead(
                id=record.id,
                name=record.name,
                version=version,
                transport=record.transport,
                config_ref=record.config_ref,
                enabled=record.enabled,
                health_status=record.health_status,
                last_checked_at=record.last_checked_at,
                tool_count=tool_count,
                error_code=error_code,
            )
        )
    await session.commit()
    return result


@mcp_router.get("/tools", response_model=list[MCPToolRead])
async def list_mcp_tools(_: TechnicalUser, session: DatabaseSession) -> list[MCPToolRead]:
    server_name, _, discovered = await mcp_client.discover()
    discovered_names = {tool.name for tool in discovered}
    policies = {
        policy.tool_name: policy for policy in (await session.scalars(select(ToolPolicy))).all()
    }
    result: list[MCPToolRead] = []
    for definition in tool_registry.definitions():
        if definition.source != "MCP" or definition.external_name not in discovered_names:
            continue
        policy = policies.get(definition.name)
        if policy is None:
            continue
        result.append(
            MCPToolRead(
                id=definition.name,
                server_name=server_name,
                external_name=definition.external_name or definition.name,
                description=definition.description,
                input_schema=definition.input_model.model_json_schema(),
                output_schema={"type": "object", "additionalProperties": True},
                allowed_roles=list(policy.allowed_roles),
                read_only=policy.read_only,
                enabled=policy.enabled,
                timeout_ms=definition.timeout_ms,
                max_calls_per_run=policy.max_calls_per_run,
            )
        )
    return result


@mcp_router.post("/tools/{tool_id:path}/test", response_model=MCPToolTestResponse)
async def test_mcp_tool(
    tool_id: str,
    body: MCPToolTestRequest,
    user: TechnicalUser,
    session: DatabaseSession,
) -> MCPToolTestResponse:
    definition = tool_registry.get(tool_id)
    if definition.source != "MCP" or definition.side_effect:
        raise AppError(403, "TOOL_NOT_ALLOWED", "仅允许测试白名单中的只读 MCP 工具")
    result = await agent_runner.run(
        session,
        user,
        [AgentCall(tool_name=tool_id, arguments=body.arguments)],
        allowed_tools={tool_id},
        max_steps=body.max_steps,
        total_timeout_seconds=body.total_timeout_seconds,
    )
    execution = result.executions[0]
    return MCPToolTestResponse(
        run=_run_summary(result.run), output=execution.output, source=execution.source
    )
