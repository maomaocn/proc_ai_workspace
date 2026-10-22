from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
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
    from app.models.approval import AgentRun, ApprovalTask
    from app.models.identity import User


class InventoryItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        CheckConstraint("available_qty >= 0", name="ck_inventory_items_available_qty"),
        CheckConstraint("reference_price > 0", name="ck_inventory_items_reference_price"),
        CheckConstraint("char_length(category) > 0", name="ck_inventory_items_category"),
        CheckConstraint("char_length(model) > 0", name="ck_inventory_items_model"),
    )

    sku: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    available_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())

    quotes: Mapped[list[SupplierQuote]] = relationship(back_populates="inventory_item")


class Supplier(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "suppliers"
    __table_args__ = (CheckConstraint("char_length(name) > 0", name="ck_suppliers_name"),)

    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    demo_data: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())

    quotes: Mapped[list[SupplierQuote]] = relationship(back_populates="supplier")


class SupplierQuote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "supplier_quotes"
    __table_args__ = (
        CheckConstraint("unit_price > 0", name="ck_supplier_quotes_unit_price"),
        CheckConstraint("currency = 'CNY'", name="ck_supplier_quotes_currency"),
        CheckConstraint("source_type = 'DEMO'", name="ck_supplier_quotes_source_type"),
        UniqueConstraint(
            "supplier_id",
            "inventory_item_id",
            "quoted_at",
            name="uq_supplier_quotes_supplier_item_time",
        ),
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    inventory_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    quoted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False, default="DEMO")

    supplier: Mapped[Supplier] = relationship(back_populates="quotes")
    inventory_item: Mapped[InventoryItem] = relationship(back_populates="quotes")


class PurchaseRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "purchase_requests"
    __table_args__ = (
        Index("ix_purchase_requests_requester_created", "requester_id", "created_at"),
        CheckConstraint("quantity > 0", name="ck_purchase_requests_quantity"),
        CheckConstraint("unit_price_limit > 0", name="ck_purchase_requests_unit_price_limit"),
        CheckConstraint("total_budget > 0", name="ck_purchase_requests_total_budget"),
        CheckConstraint("version >= 0", name="ck_purchase_requests_version"),
        CheckConstraint(
            "priority IN ('LOW', 'NORMAL', 'HIGH')",
            name="ck_purchase_requests_priority",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'SUBMITTED', 'PENDING_APPROVAL', 'APPROVED', "
            "'REJECTED', 'ORDERED', 'RECEIVED', 'CLOSED', 'CANCELLED')",
            name="ck_purchase_requests_status",
        ),
    )

    requester_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    item_description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_budget: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    purpose: Mapped[str] = mapped_column(String(500), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="NORMAL")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT", index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    linked_run_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    requester: Mapped[User] = relationship(foreign_keys=[requester_id])
    candidates: Mapped[list[PurchaseCandidate]] = relationship(
        back_populates="request",
        cascade="all, delete-orphan",
        order_by="PurchaseCandidate.total_price",
    )
    approval_tasks: Mapped[list[ApprovalTask]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="ApprovalTask.stage"
    )
    workflow_runs: Mapped[list[AgentRun]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="AgentRun.created_at"
    )


class PurchaseCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "purchase_candidates"
    __table_args__ = (
        UniqueConstraint(
            "request_id", "source_quote_id", name="uq_purchase_candidates_request_quote"
        ),
        CheckConstraint("quantity > 0", name="ck_purchase_candidates_quantity"),
        CheckConstraint("unit_price > 0", name="ck_purchase_candidates_unit_price"),
        CheckConstraint("total_price > 0", name="ck_purchase_candidates_total_price"),
    )

    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("purchase_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    source_quote_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_quotes.id", ondelete="RESTRICT"), nullable=False
    )

    request: Mapped[PurchaseRequest] = relationship(back_populates="candidates")
    item: Mapped[InventoryItem] = relationship()
    supplier: Mapped[Supplier] = relationship()
    source_quote: Mapped[SupplierQuote] = relationship()
