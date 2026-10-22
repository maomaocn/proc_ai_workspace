"""add M5 MCP, harness and observability tables

Revision ID: 20261022_0006
Revises: 20261022_0005
Create Date: 2026-10-22 10:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261022_0006"
down_revision: str | Sequence[str] | None = "20261022_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_agent_runs_status", "agent_runs", type_="check")
    op.create_check_constraint(
        "ck_agent_runs_status",
        "agent_runs",
        "status IN ('CREATED', 'RUNNING', 'WAITING_USER', 'WAITING_APPROVAL', "
        "'SUCCEEDED', 'FAILED', 'CANCELLED')",
    )
    op.alter_column("agent_runs", "request_id", existing_type=sa.Uuid(), nullable=True)
    op.alter_column(
        "agent_runs", "graph_thread_id", existing_type=sa.String(length=255), nullable=True
    )
    op.add_column(
        "agent_runs",
        sa.Column("run_type", sa.String(length=24), server_default="WORKFLOW", nullable=False),
    )
    op.add_column(
        "agent_runs", sa.Column("max_steps", sa.Integer(), server_default="12", nullable=False)
    )
    op.add_column(
        "agent_runs",
        sa.Column("total_timeout_ms", sa.Integer(), server_default="90000", nullable=False),
    )
    op.add_column(
        "agent_runs", sa.Column("step_count", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "agent_runs",
        sa.Column("tool_call_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "agent_runs", sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False)
    )
    op.create_check_constraint(
        "ck_agent_runs_run_type", "agent_runs", "run_type IN ('WORKFLOW', 'HARNESS')"
    )
    op.create_check_constraint("ck_agent_runs_max_steps", "agent_runs", "max_steps > 0")
    op.create_check_constraint("ck_agent_runs_total_timeout", "agent_runs", "total_timeout_ms > 0")
    op.add_column(
        "agent_steps", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True)
    )

    op.create_table(
        "mcp_servers",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("transport", sa.String(length=24), nullable=False),
        sa.Column("config_ref", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("health_status", sa.String(length=24), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "health_status IN ('UNKNOWN', 'HEALTHY', 'UNHEALTHY')",
            name="ck_mcp_servers_health",
        ),
        sa.CheckConstraint("transport IN ('stdio')", name="ck_mcp_servers_transport"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "tool_policies",
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("allowed_roles", sa.JSON(), nullable=False),
        sa.Column("read_only", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("max_calls_per_run", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("max_calls_per_run > 0", name="ck_tool_policies_max_calls"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tool_name"),
    )
    op.create_table(
        "agent_events",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("data_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("seq > 0", name="ck_agent_events_seq"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "seq", name="uq_agent_events_run_seq"),
    )
    op.create_index(
        "ix_agent_events_run_created", "agent_events", ["run_id", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_agent_events_run_created", table_name="agent_events")
    op.drop_table("agent_events")
    op.drop_table("tool_policies")
    op.drop_table("mcp_servers")
    op.drop_column("agent_steps", "finished_at")
    op.drop_constraint("ck_agent_runs_total_timeout", "agent_runs", type_="check")
    op.drop_constraint("ck_agent_runs_max_steps", "agent_runs", type_="check")
    op.drop_constraint("ck_agent_runs_run_type", "agent_runs", type_="check")
    op.drop_column("agent_runs", "retry_count")
    op.drop_column("agent_runs", "tool_call_count")
    op.drop_column("agent_runs", "step_count")
    op.drop_column("agent_runs", "total_timeout_ms")
    op.drop_column("agent_runs", "max_steps")
    op.drop_column("agent_runs", "run_type")
    op.alter_column(
        "agent_runs", "graph_thread_id", existing_type=sa.String(length=255), nullable=False
    )
    op.alter_column("agent_runs", "request_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_constraint("ck_agent_runs_status", "agent_runs", type_="check")
    op.create_check_constraint(
        "ck_agent_runs_status",
        "agent_runs",
        "status IN ('CREATED', 'RUNNING', 'WAITING_APPROVAL', 'SUCCEEDED', 'FAILED', 'CANCELLED')",
    )
