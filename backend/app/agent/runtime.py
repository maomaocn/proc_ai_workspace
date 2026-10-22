import asyncio
from contextlib import AbstractAsyncContextManager
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command

from app.agent.graph import build_approval_graph
from app.agent.state import GraphState
from app.core.config import settings


class WorkflowRuntime:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._context: AbstractAsyncContextManager[AsyncPostgresSaver] | None = None
        self._saver: AsyncPostgresSaver | None = None
        self._graph: Any | None = None

    async def start(self) -> None:
        if self._graph is not None:
            return
        async with self._lock:
            if self._graph is not None:
                return
            context = AsyncPostgresSaver.from_conn_string(
                settings.effective_checkpoint_database_url
            )
            saver = await context.__aenter__()
            try:
                await saver.setup()
                graph = build_approval_graph(saver)
            except Exception:
                await context.__aexit__(None, None, None)
                raise
            self._context = context
            self._saver = saver
            self._graph = graph

    async def close(self) -> None:
        async with self._lock:
            if self._context is not None:
                await self._context.__aexit__(None, None, None)
            self._context = None
            self._saver = None
            self._graph = None

    async def begin(self, state: GraphState, thread_id: str) -> dict[str, Any]:
        await self.start()
        result = await self._graph.ainvoke(
            state,
            self._config(thread_id),
            durability="sync",
        )
        if not result.get("__interrupt__"):
            raise RuntimeError("approval workflow did not pause for human approval")
        return await self.snapshot(thread_id)

    async def resume(self, thread_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        await self.start()
        await self._graph.ainvoke(
            Command(resume=payload),
            self._config(thread_id),
            durability="sync",
        )
        return await self.snapshot(thread_id)

    async def snapshot(self, thread_id: str) -> dict[str, Any]:
        await self.start()
        snapshot = await self._graph.aget_state(self._config(thread_id))
        interrupts = [item.value for task in snapshot.tasks for item in task.interrupts]
        return {
            "values": dict(snapshot.values),
            "next": list(snapshot.next),
            "interrupts": interrupts,
            "checkpoint_id": snapshot.config.get("configurable", {}).get("checkpoint_id"),
            "created_at": snapshot.created_at,
        }

    async def delete_thread(self, thread_id: str) -> None:
        """Delete one checkpoint thread, primarily for isolated test teardown."""
        await self.start()
        await self._saver.adelete_thread(thread_id)

    def _config(self, thread_id: str) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": thread_id}}


workflow_runtime = WorkflowRuntime()
