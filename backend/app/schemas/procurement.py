import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.approval import ApprovalTaskRead, AuditEventRead, WorkflowRunRead
from app.schemas.knowledge import SearchResponse

PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
Priority = Literal["LOW", "NORMAL", "HIGH"]
PurchaseStatus = Literal[
    "DRAFT",
    "SUBMITTED",
    "PENDING_APPROVAL",
    "APPROVED",
    "REJECTED",
    "ORDERED",
    "RECEIVED",
    "CLOSED",
    "CANCELLED",
]


def _strip(value: str) -> str:
    return " ".join(value.split())


class InventoryItemCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    category: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=200)
    available_qty: int = Field(ge=0, le=1_000_000)
    reference_price: PositiveMoney
    active: bool = True

    @field_validator("sku", "category", "model")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return _strip(value)


class InventoryItemUpdate(BaseModel):
    category: str | None = Field(default=None, min_length=1, max_length=100)
    model: str | None = Field(default=None, min_length=1, max_length=200)
    available_qty: int | None = Field(default=None, ge=0, le=1_000_000)
    reference_price: PositiveMoney | None = None
    active: bool | None = None

    @field_validator("category", "model")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _strip(value) if value is not None else None


class InventoryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    category: str
    model: str
    available_qty: int
    reference_price: Decimal
    active: bool
    created_at: datetime
    updated_at: datetime


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    active: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _strip(value)


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    active: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        return _strip(value) if value is not None else None


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    active: bool
    demo_data: bool
    created_at: datetime
    updated_at: datetime


class SupplierSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    active: bool
    demo_data: bool


class InventoryItemSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    category: str
    model: str
    available_qty: int
    reference_price: Decimal
    active: bool


class SupplierQuoteCreate(BaseModel):
    supplier_id: uuid.UUID
    inventory_item_id: uuid.UUID
    unit_price: PositiveMoney
    quoted_at: datetime


class SupplierQuoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    supplier_id: uuid.UUID
    inventory_item_id: uuid.UUID
    unit_price: Decimal
    currency: Literal["CNY"]
    quoted_at: datetime
    source_type: Literal["DEMO"]
    supplier: SupplierSummary
    inventory_item: InventoryItemSummary
    created_at: datetime


class PurchaseRequestCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=100)
    item_description: str = Field(min_length=1, max_length=500)
    quantity: int = Field(gt=0, le=100_000)
    unit_price_limit: PositiveMoney
    total_budget: PositiveMoney | None = None
    purpose: str = Field(min_length=1, max_length=500)
    priority: Priority = "NORMAL"
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("title", "category", "item_description", "purpose")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _strip(value)

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def calculate_total_budget(self) -> "PurchaseRequestCreate":
        self.total_budget = (self.unit_price_limit * self.quantity).quantize(Decimal("0.01"))
        return self


class PurchaseRequestUpdate(BaseModel):
    version: int = Field(ge=0)
    title: str | None = Field(default=None, min_length=1, max_length=160)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    item_description: str | None = Field(default=None, min_length=1, max_length=500)
    quantity: int | None = Field(default=None, gt=0, le=100_000)
    unit_price_limit: PositiveMoney | None = None
    total_budget: PositiveMoney | None = None
    purpose: str | None = Field(default=None, min_length=1, max_length=500)
    priority: Priority | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("title", "category", "item_description", "purpose")
    @classmethod
    def normalize_optional_required_text(cls, value: str | None) -> str | None:
        return _strip(value) if value is not None else None

    @field_validator("notes")
    @classmethod
    def normalize_optional_notes(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class RequesterSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str


class PurchaseCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_id: uuid.UUID
    item_id: uuid.UUID
    supplier_id: uuid.UUID
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    source_quote_id: uuid.UUID
    item: InventoryItemSummary
    supplier: SupplierSummary
    source_quote: SupplierQuoteRead
    stock_sufficient: bool
    within_unit_limit: bool
    within_total_budget: bool


class PurchaseRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requester_id: uuid.UUID
    requester: RequesterSummary
    title: str
    category: str
    item_description: str
    quantity: int
    unit_price_limit: Decimal
    total_budget: Decimal
    purpose: str
    priority: Priority
    notes: str | None
    status: PurchaseStatus
    version: int
    linked_run_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class PurchaseRequestDetail(PurchaseRequestRead):
    candidates: list[PurchaseCandidateRead]
    approval_tasks: list[ApprovalTaskRead] = []
    workflow_run: WorkflowRunRead | None = None
    audit_events: list[AuditEventRead] = []


class ToolCallRead(BaseModel):
    name: str
    duration_ms: int
    source: Literal["DATABASE", "MOCK_RAG"]
    item_count: int


class ProcurementPlanResponse(BaseModel):
    procurement: PurchaseRequestDetail
    policy: SearchResponse
    tool_calls: list[ToolCallRead]
    source: Literal["DEMO"] = "DEMO"


FulfillmentStatus = Literal["ORDERED", "RECEIVED", "CLOSED"]


class FulfillmentTransitionRequest(BaseModel):
    target_status: FulfillmentStatus
    version: int = Field(ge=0)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class FulfillmentTransitionResponse(BaseModel):
    request_id: uuid.UUID
    previous_status: str
    purchase_status: FulfillmentStatus
    version: int
    audit_event_id: uuid.UUID
    source: Literal["DEMO"] = "DEMO"
    idempotent_replay: bool = False
