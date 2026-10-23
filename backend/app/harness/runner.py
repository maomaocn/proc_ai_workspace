from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.harness.redaction import summarize
from app.models.approval import AgentEvent, AgentRun, AgentStep, ToolPolicy
from app.models.identity import User
from app.tools.registry import ToolExecution, ToolRegistry, tool_registry


@dataclass(frozen=True)
class AgentCall:
    tool_name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class AgentRunResult:
    run: AgentRun
    executions: list[ToolExecution]


class AgentRunner:
    """A minimal bounded executor for an already-planned list of tool calls.

    It is intentionally not an LLM planner. Its job is to enforce policy, limits, retries and
    durable traces around ToolRegistry calls so a future planner cannot bypass these controls.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    async def run(
        self,
        session: AsyncSession,
        user: User,
        calls: list[AgentCall],
        *,
        allowed_tools: set[str],
        max_steps: int | None = None,
        total_timeout_seconds: float | None = None,
    ) -> AgentRunResult:
        actual_max_steps = max_steps or settings.agent_max_steps
        actual_timeout = total_timeout_seconds or settings.agent_total_timeout_seconds
        if actual_max_steps < 1 or actual_max_steps > settings.agent_max_steps:
            raise AppError(400, "HARNESS_LIMIT_INVALID", "max_steps 超出允许范围")
        if actual_timeout <= 0 or actual_timeout > settings.agent_total_timeout_seconds:
            raise AppError(400, "HARNESS_LIMIT_INVALID", "总超时超出允许范围")

        now = datetime.now(UTC)
        # AgentRun/Step/Event are observability memory: they explain what ran, but are not fed back
        # into the model as conversational or planning context.
        run = AgentRun(
            user_id=user.id,
            request_id=None,
            graph_thread_id=None,
            run_type="HARNESS",
            status="RUNNING",
            started_at=now,
            model_provider=settings.model_provider,
            max_steps=actual_max_steps,
            total_timeout_ms=round(actual_timeout * 1000),
            step_count=0,
            tool_call_count=0,
            retry_count=0,
            steps=[],
            events=[],
        )
        session.add(run)
        await session.flush()
        self._event(run, "run.started", {"status": "RUNNING"})

        if len(calls) > actual_max_steps:
            error = AppError(422, "STEP_LIMIT_EXCEEDED", "Agent 执行步数超过上限")
            self._failed_step(run, 0, "guardrails", None, {}, error.code)
            await self._fail(session, run, error)

        executions: list[ToolExecution] = []
        call_counts: dict[str, int] = {}
        try:
            async with asyncio.timeout(actual_timeout):
                for call in calls:
                    try:
                        policy = await self._authorize(
                            session, user, call, allowed_tools, call_counts
                        )
                    except AppError as error:
                        self._failed_step(
                            run,
                            run.step_count,
                            "authorize_tool",
                            call.tool_name,
                            call.arguments,
                            error.code,
                        )
                        raise
                    execution = await self._execute_call(
                        session,
                        user,
                        run,
                        call,
                        policy,
                        actual_max_steps,
                    )
                    executions.append(execution)
                    call_counts[call.tool_name] = call_counts.get(call.tool_name, 0) + 1
        except TimeoutError:
            error = AppError(503, "RUN_TIMEOUT", "Agent 运行超过总超时")
            await self._fail(session, run, error)
        except AppError as error:
            await self._fail(session, run, error)

        run.status = "SUCCEEDED"
        run.finished_at = datetime.now(UTC)
        self._event(run, "run.completed", {"status": run.status})
        await session.commit()
        return AgentRunResult(run=run, executions=executions)

    async def _authorize(
        self,
        session: AsyncSession,
        user: User,
        call: AgentCall,
        allowed_tools: set[str],
        call_counts: dict[str, int],
    ) -> ToolPolicy:
        # Authorization is deliberately layered: per-run allowlist, static registry roles, then
        # mutable database policy and per-run call quota.
        if call.tool_name not in allowed_tools:
            raise AppError(403, "TOOL_NOT_ALLOWED", "工具不在本次运行白名单中")
        definition = self.registry.get(call.tool_name)
        if user.roles.isdisjoint(definition.allowed_roles):
            raise AppError(403, "TOOL_NOT_ALLOWED", "当前角色无权调用此工具")
        policy = await session.scalar(
            select(ToolPolicy).where(ToolPolicy.tool_name == call.tool_name)
        )
        if policy is None or not policy.enabled or not policy.read_only:
            raise AppError(403, "TOOL_NOT_ALLOWED", "工具策略未启用只读调用")
        if user.roles.isdisjoint(set(policy.allowed_roles)):
            raise AppError(403, "TOOL_NOT_ALLOWED", "当前角色不在工具策略授权范围")
        if call_counts.get(call.tool_name, 0) >= policy.max_calls_per_run:
            raise AppError(422, "TOOL_CALL_LIMIT_EXCEEDED", "工具调用次数超过策略上限")
        return policy

    async def _execute_call(
        self,
        session: AsyncSession,
        user: User,
        run: AgentRun,
        call: AgentCall,
        policy: ToolPolicy,
        max_steps: int,
    ) -> ToolExecution:
        definition = self.registry.get(call.tool_name)
        # Automatic retries are limited to read-only tools to avoid repeating external side effects.
        max_attempts = settings.tool_retry_max_attempts if policy.read_only else 1
        last_error: AppError | None = None
        for attempt in range(max_attempts):
            if run.step_count >= max_steps:
                raise AppError(422, "STEP_LIMIT_EXCEEDED", "Agent 执行步数超过上限")
            index = run.step_count
            started = datetime.now(UTC)
            step = AgentStep(
                run=run,
                step_index=index,
                node_name="mcp_tool_call" if definition.source == "MCP" else "tool_call",
                tool_name=call.tool_name,
                status="RUNNING",
                started_at=started,
                input_summary=summarize(call.arguments),
            )
            run.step_count += 1
            run.tool_call_count += 1
            if attempt > 0:
                run.retry_count += 1
            session.add(step)
            self._event(
                run,
                "tool.started",
                {"tool_name": call.tool_name, "status": "RUNNING", "attempt": attempt + 1},
            )
            try:
                execution = await self.registry.invoke(
                    call.tool_name, call.arguments, user, session
                )
            except AppError as error:
                step.status = "FAILED"
                step.error_code = error.code
                step.finished_at = datetime.now(UTC)
                step.duration_ms = max(
                    0, round((step.finished_at - step.started_at).total_seconds() * 1000)
                )
                self._event(
                    run,
                    "tool.completed",
                    {"tool_name": call.tool_name, "status": "FAILED", "error_code": error.code},
                )
                last_error = error
                retryable = error.code in {
                    "TOOL_TIMEOUT",
                    "MCP_UNAVAILABLE",
                    "MCP_TOOL_ERROR",
                }
                if not retryable or attempt + 1 >= max_attempts:
                    raise
                await asyncio.sleep(settings.tool_retry_backoff_ms / 1000 * (2**attempt))
                continue

            step.status = "SUCCEEDED"
            step.finished_at = datetime.now(UTC)
            step.duration_ms = execution.duration_ms
            step.output_summary = summarize(execution.output)
            self._event(
                run,
                "tool.completed",
                {"tool_name": call.tool_name, "status": "SUCCEEDED"},
            )
            return execution
        raise last_error or AppError(503, "TOOL_UNAVAILABLE", "工具执行失败")

    async def _fail(self, session: AsyncSession, run: AgentRun, error: AppError) -> None:
        run.status = "FAILED"
        run.error_code = error.code
        run.finished_at = datetime.now(UTC)
        self._event(
            run,
            "run.failed",
            {"status": "FAILED", "error_code": error.code},
        )
        await session.commit()
        details = {**error.details, "run_id": str(run.id)}
        raise AppError(error.status_code, error.code, error.message, details) from error

    def _failed_step(
        self,
        run: AgentRun,
        index: int,
        node_name: str,
        tool_name: str | None,
        payload: dict[str, Any],
        error_code: str,
    ) -> None:
        now = datetime.now(UTC)
        run.steps.append(
            AgentStep(
                step_index=index,
                node_name=node_name,
                tool_name=tool_name,
                status="FAILED",
                error_code=error_code,
                started_at=now,
                finished_at=now,
                duration_ms=0,
                input_summary=summarize(payload),
            )
        )
        run.step_count += 1

    @staticmethod
    def _event(run: AgentRun, event_type: str, payload: dict[str, Any]) -> None:
        seq = len(run.events) + 1
        now = datetime.now(UTC)
        run.events.append(
            AgentEvent(
                seq=seq,
                event_type=event_type,
                data_json={
                    "run_id": str(run.id),
                    "seq": seq,
                    "timestamp": now.isoformat(),
                    **payload,
                },
            )
        )


agent_runner = AgentRunner(tool_registry)
