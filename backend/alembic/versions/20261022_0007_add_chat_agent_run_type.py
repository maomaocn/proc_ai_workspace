"""add chat agent run type

Revision ID: 20261022_0007
Revises: 20261022_0006
Create Date: 2026-10-22 15:30:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261022_0007"
down_revision: str | Sequence[str] | None = "20261022_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_agent_runs_run_type", "agent_runs", type_="check")
    op.create_check_constraint(
        "ck_agent_runs_run_type",
        "agent_runs",
        "run_type IN ('WORKFLOW', 'HARNESS', 'CHAT')",
    )


def downgrade() -> None:
    op.execute("UPDATE agent_runs SET run_type = 'HARNESS' WHERE run_type = 'CHAT'")
    op.drop_constraint("ck_agent_runs_run_type", "agent_runs", type_="check")
    op.create_check_constraint(
        "ck_agent_runs_run_type",
        "agent_runs",
        "run_type IN ('WORKFLOW', 'HARNESS')",
    )
