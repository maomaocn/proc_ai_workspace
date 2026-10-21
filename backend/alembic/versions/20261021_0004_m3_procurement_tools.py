"""Add M3 inventory, supplier, quote, procurement, and candidate tables.

Revision ID: 20261021_0004
Revises: 20261021_0003
Create Date: 2026-10-21 21:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261021_0004"
down_revision: str | Sequence[str] | None = "20261021_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "inventory_items",
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("available_qty", sa.Integer(), nullable=False),
        sa.Column("reference_price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint("available_qty >= 0", name="ck_inventory_items_available_qty"),
        sa.CheckConstraint("char_length(category) > 0", name="ck_inventory_items_category"),
        sa.CheckConstraint("char_length(model) > 0", name="ck_inventory_items_model"),
        sa.CheckConstraint("reference_price > 0", name="ck_inventory_items_reference_price"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inventory_items_category"), "inventory_items", ["category"])
    op.create_index(op.f("ix_inventory_items_sku"), "inventory_items", ["sku"], unique=True)

    op.create_table(
        "suppliers",
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("demo_data", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint("char_length(name) > 0", name="ck_suppliers_name"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "supplier_quotes",
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("inventory_item_id", sa.Uuid(), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("quoted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint("currency = 'CNY'", name="ck_supplier_quotes_currency"),
        sa.CheckConstraint("source_type = 'DEMO'", name="ck_supplier_quotes_source_type"),
        sa.CheckConstraint("unit_price > 0", name="ck_supplier_quotes_unit_price"),
        sa.ForeignKeyConstraint(
            ["inventory_item_id"], ["inventory_items.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "supplier_id",
            "inventory_item_id",
            "quoted_at",
            name="uq_supplier_quotes_supplier_item_time",
        ),
    )
    op.create_index(
        op.f("ix_supplier_quotes_inventory_item_id"),
        "supplier_quotes",
        ["inventory_item_id"],
    )
    op.create_index(
        op.f("ix_supplier_quotes_supplier_id"), "supplier_quotes", ["supplier_id"]
    )

    op.create_table(
        "purchase_requests",
        sa.Column("requester_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("item_description", sa.String(length=500), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_limit", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total_budget", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("purpose", sa.String(length=500), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("linked_run_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "priority IN ('LOW', 'NORMAL', 'HIGH')", name="ck_purchase_requests_priority"
        ),
        sa.CheckConstraint("quantity > 0", name="ck_purchase_requests_quantity"),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'SUBMITTED', 'PENDING_APPROVAL', 'APPROVED', "
            "'REJECTED', 'ORDERED', 'RECEIVED', 'CLOSED', 'CANCELLED')",
            name="ck_purchase_requests_status",
        ),
        sa.CheckConstraint("total_budget > 0", name="ck_purchase_requests_total_budget"),
        sa.CheckConstraint(
            "unit_price_limit > 0", name="ck_purchase_requests_unit_price_limit"
        ),
        sa.CheckConstraint("version >= 0", name="ck_purchase_requests_version"),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_purchase_requests_category"), "purchase_requests", ["category"]
    )
    op.create_index(
        op.f("ix_purchase_requests_linked_run_id"), "purchase_requests", ["linked_run_id"]
    )
    op.create_index(
        "ix_purchase_requests_requester_created",
        "purchase_requests",
        ["requester_id", "created_at"],
    )
    op.create_index(op.f("ix_purchase_requests_status"), "purchase_requests", ["status"])

    op.create_table(
        "purchase_candidates",
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total_price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("source_quote_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint("quantity > 0", name="ck_purchase_candidates_quantity"),
        sa.CheckConstraint("total_price > 0", name="ck_purchase_candidates_total_price"),
        sa.CheckConstraint("unit_price > 0", name="ck_purchase_candidates_unit_price"),
        sa.ForeignKeyConstraint(["item_id"], ["inventory_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["request_id"], ["purchase_requests.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_quote_id"], ["supplier_quotes.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "request_id", "source_quote_id", name="uq_purchase_candidates_request_quote"
        ),
    )
    op.create_index(
        op.f("ix_purchase_candidates_request_id"), "purchase_candidates", ["request_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_purchase_candidates_request_id"), table_name="purchase_candidates")
    op.drop_table("purchase_candidates")
    op.drop_index(op.f("ix_purchase_requests_status"), table_name="purchase_requests")
    op.drop_index("ix_purchase_requests_requester_created", table_name="purchase_requests")
    op.drop_index(op.f("ix_purchase_requests_linked_run_id"), table_name="purchase_requests")
    op.drop_index(op.f("ix_purchase_requests_category"), table_name="purchase_requests")
    op.drop_table("purchase_requests")
    op.drop_index(op.f("ix_supplier_quotes_supplier_id"), table_name="supplier_quotes")
    op.drop_index(op.f("ix_supplier_quotes_inventory_item_id"), table_name="supplier_quotes")
    op.drop_table("supplier_quotes")
    op.drop_table("suppliers")
    op.drop_index(op.f("ix_inventory_items_sku"), table_name="inventory_items")
    op.drop_index(op.f("ix_inventory_items_category"), table_name="inventory_items")
    op.drop_table("inventory_items")
