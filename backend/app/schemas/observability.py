from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class RunSummary(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    username: str
    request_id: uuid.UUID | None
    graph_thread_id: str | None
    run_type: Literal["WORKFLOW", "HARNESS"]
    status: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    error_code: str | None
    model_provider: str
    max_steps: int
    total_timeout_ms: int
    step_count: int
    tool_call_count: int
    retry_count: int


class AgentStepRead(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    step_index: int
    node_name: str
    tool_name: str | None
    status: str
    duration_ms: int | None
    input_summary: str | None
    output_summary: str | None
    error_code: str | None
    started_at: datetime
    finished_at: datetime | None


class AgentRunDetail(RunSummary):
    steps: list[AgentStepRead]


class WorkflowEdge(BaseModel):
    source: str
    target: str


class WorkflowRunDetail(BaseModel):
    run: RunSummary
    business_number: str | None
    nodes: list[AgentStepRead]
    edges: list[WorkflowEdge]


class MCPServerRead(BaseModel):
    id: uuid.UUID
    name: str
    version: str | None
    transport: str
    config_ref: str
    enabled: bool
    health_status: str
    last_checked_at: datetime | None
    tool_count: int
    error_code: str | None = None


class MCPToolRead(BaseModel):
    id: str
    server_name: str
    external_name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    allowed_roles: list[str]
    read_only: bool
    enabled: bool
    timeout_ms: int
    max_calls_per_run: int


class MCPToolTestRequest(BaseModel):
    arguments: dict[str, Any]
    max_steps: int | None = Field(default=None, ge=1, le=50)
    total_timeout_seconds: float | None = Field(default=None, gt=0, le=300)


class MCPToolTestResponse(BaseModel):
    run: RunSummary
    output: dict[str, Any]
    source: str
