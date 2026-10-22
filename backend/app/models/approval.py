from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.identity import User
    from app.models.procurement import PurchaseRequest


class ApprovalRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "approval_rules"
    __table_args__ = (
        CheckConstraint("min_amount >= 0", name="ck_approval_rules_min_amount"),
        CheckConstraint(
            "max_amount IS NULL OR max_amount > min_amount",
            name="ck_approval_rules_amount_range",
        ),
        CheckConstraint("stage > 0", name="ck_approval_rules_stage"),
        CheckConstraint("approver_role IN ('APPROVER')", name="ck_approval_rules_approver_role"),
        Index("ix_approval_rules_active_range", "active", "min_amount", "max_amount"),
    )

    min_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    stage: Mapped[int] = mapped_column(Integer, nullable=False)
    approver_role: Mapped[str] = mapped_column(String(32), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())


class ApprovalTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "approval_tasks"
    __table_args__ = (
        UniqueConstraint(
            "request_id", "stage", "assignee_id", name="uq_approval_tasks_request_stage_assignee"
        ),
        CheckConstraint("stage > 0", name="ck_approval_tasks_stage"),
        CheckConstraint(
            "status IN ('WAITING', 'PENDING', 'APPROVED', 'REJECTED', 'SKIPPED')",
            name="ck_approval_tasks_status",
        ),
        Index("ix_approval_tasks_assignee_status", "assignee_id", "status"),
    )

    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("purchase_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[int] = mapped_column(Integer, nullable=False)
    approver_role: Mapped[str] = mapped_column(String(32), nullable=False)
    assignee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="WAITING")
    decision_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    request: Mapped[PurchaseRequest] = relationship(back_populates="approval_tasks")
    assignee: Mapped[User] = relationship(foreign_keys=[assignee_id])
    decisions: Mapped[list[ApprovalDecision]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class ApprovalDecision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "approval_decisions"
    __table_args__ = (
        UniqueConstraint("actor_id", "idempotency_key", name="uq_approval_decisions_actor_key"),
        CheckConstraint("action IN ('APPROVE', 'REJECT')", name="ck_approval_decisions_action"),
    )

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("approval_tasks.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    task: Mapped[ApprovalTask] = relationship(back_populates="decisions")
    actor: Mapped[User] = relationship(foreign_keys=[actor_id])


class AgentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('CREATED', 'RUNNING', 'WAITING_USER', 'WAITING_APPROVAL', "
            "'SUCCEEDED', 'FAILED', 'CANCELLED')",
            name="ck_agent_runs_status",
        ),
        CheckConstraint("max_steps > 0", name="ck_agent_runs_max_steps"),
        CheckConstraint("total_timeout_ms > 0", name="ck_agent_runs_total_timeout"),
        CheckConstraint("run_type IN ('WORKFLOW', 'HARNESS')", name="ck_agent_runs_run_type"),
        Index("ix_agent_runs_user_status", "user_id", "status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("purchase_requests.id", ondelete="CASCADE"), nullable=True, index=True
    )
    graph_thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    run_type: Mapped[str] = mapped_column(String(24), nullable=False, default="WORKFLOW")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="CREATED")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="mock")
    max_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    total_timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=90000)
    step_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user: Mapped[User] = relationship(foreign_keys=[user_id])
    request: Mapped[PurchaseRequest | None] = relationship(back_populates="workflow_runs")
    steps: Mapped[list[AgentStep]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="AgentStep.step_index"
    )
    events: Mapped[list[AgentEvent]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="AgentEvent.seq"
    )


class AgentStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_steps"
    __table_args__ = (
        UniqueConstraint("run_id", "step_index", name="uq_agent_steps_run_index"),
        CheckConstraint("step_index >= 0", name="ck_agent_steps_index"),
        CheckConstraint(
            "status IN ('RUNNING', 'SUCCEEDED', 'FAILED', 'WAITING', 'SKIPPED')",
            name="ck_agent_steps_status",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    node_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped[AgentRun] = relationship(back_populates="steps")


class AgentEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_events"
    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uq_agent_events_run_seq"),
        CheckConstraint("seq > 0", name="ck_agent_events_seq"),
        Index("ix_agent_events_run_created", "run_id", "created_at"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    data_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    run: Mapped[AgentRun] = relationship(back_populates="events")


class MCPServerRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mcp_servers"
    __table_args__ = (
        CheckConstraint("transport IN ('stdio')", name="ck_mcp_servers_transport"),
        CheckConstraint(
            "health_status IN ('UNKNOWN', 'HEALTHY', 'UNHEALTHY')",
            name="ck_mcp_servers_health",
        ),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    transport: Mapped[str] = mapped_column(String(24), nullable=False, default="stdio")
    config_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    health_status: Mapped[str] = mapped_column(String(24), nullable=False, default="UNKNOWN")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ToolPolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tool_policies"
    __table_args__ = (CheckConstraint("max_calls_per_run > 0", name="ck_tool_policies_max_calls"),)

    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    allowed_roles: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    read_only: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    max_calls_per_run: Mapped[int] = mapped_column(Integer, nullable=False, default=4)


class AuditEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_resource", "resource_type", "resource_id", "created_at"),
    )

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    request_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)

    actor: Mapped[User | None] = relationship(foreign_keys=[actor_id])


class IdempotencyRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "actor_id", "operation", "idempotency_key", name="uq_idempotency_actor_operation_key"
        ),
    )

    actor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    response_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class WorkflowResumeEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_resume_events"
    __table_args__ = (
        UniqueConstraint("decision_id", name="uq_workflow_resume_events_decision"),
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSED', 'FAILED')",
            name="ck_workflow_resume_events_status",
        ),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("approval_decisions.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
