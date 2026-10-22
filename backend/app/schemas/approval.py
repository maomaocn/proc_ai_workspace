import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Money = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
TaskStatus = Literal["WAITING", "PENDING", "APPROVED", "REJECTED", "SKIPPED"]


class ApprovalRuleCreate(BaseModel):
    min_amount: Money
    max_amount: Money | None = None
    stage: int = Field(gt=0, le=20)
    approver_role: Literal["APPROVER"] = "APPROVER"
    active: bool = True

    @model_validator(mode="after")
    def validate_range(self) -> "ApprovalRuleCreate":
        if self.max_amount is not None and self.max_amount <= self.min_amount:
            raise ValueError("max_amount must be greater than min_amount")
        return self


class ApprovalRuleUpdate(BaseModel):
    min_amount: Money | None = None
    max_amount: Money | None = None
    stage: int | None = Field(default=None, gt=0, le=20)
    approver_role: Literal["APPROVER"] | None = None
    active: bool | None = None


class ApprovalRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    min_amount: Decimal
    max_amount: Decimal | None
    stage: int
    approver_role: str
    active: bool
    created_at: datetime
    updated_at: datetime


class ApprovalUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str


class ApprovalDecisionCreate(BaseModel):
    action: Literal["APPROVE", "REJECT"]
    comment: str | None = Field(default=None, max_length=500)

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None

    @model_validator(mode="after")
    def require_rejection_reason(self) -> "ApprovalDecisionCreate":
        if self.action == "REJECT" and (self.comment is None or len(self.comment) < 5):
            raise ValueError("驳回理由必须为 5 到 500 个字符")
        return self


class ApprovalDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    actor_id: uuid.UUID
    actor: ApprovalUserRead
    action: Literal["APPROVE", "REJECT"]
    comment: str | None
    idempotency_key: uuid.UUID
    created_at: datetime


class ApprovalTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_id: uuid.UUID
    stage: int
    approver_role: str
    assignee_id: uuid.UUID
    assignee: ApprovalUserRead
    status: TaskStatus
    decision_comment: str | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime
    decisions: list[ApprovalDecisionRead] = []


class ApprovalInboxItem(BaseModel):
    task: ApprovalTaskRead
    request_title: str
    requester_username: str
    total_budget: Decimal
    purchase_status: str
    submitted_at: datetime


class ApprovalCandidateRead(BaseModel):
    id: uuid.UUID
    sku: str
    model: str
    supplier_name: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    source_type: Literal["DEMO"] = "DEMO"


class ApprovalPurchaseRead(BaseModel):
    id: uuid.UUID
    requester_id: uuid.UUID
    requester: ApprovalUserRead
    title: str
    category: str
    item_description: str
    quantity: int
    unit_price_limit: Decimal
    total_budget: Decimal
    purpose: str
    priority: Literal["LOW", "NORMAL", "HIGH"]
    notes: str | None
    status: str
    version: int
    linked_run_id: uuid.UUID | None
    candidates: list[ApprovalCandidateRead]
    created_at: datetime
    updated_at: datetime


class ApprovalTaskDetail(BaseModel):
    task: ApprovalTaskRead
    procurement: ApprovalPurchaseRead
    approval_chain: list[ApprovalTaskRead]


class ApprovalPreviewStage(BaseModel):
    stage: int
    approver_role: str
    assignee_id: uuid.UUID
    assignee_username: str
    assignee_department: str


class ApprovalPreview(BaseModel):
    request_id: uuid.UUID
    total_budget: Decimal
    stages: list[ApprovalPreviewStage]


class WorkflowRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_id: uuid.UUID
    graph_thread_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    error_code: str | None
    model_provider: str
    checkpoint: dict[str, Any] | None = None


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: uuid.UUID
    before_json: dict[str, Any] | None
    after_json: dict[str, Any] | None
    request_id: uuid.UUID
    created_at: datetime


class ProcurementSubmissionResponse(BaseModel):
    request_id: uuid.UUID
    purchase_status: str
    version: int
    run: WorkflowRunRead
    approval_tasks: list[ApprovalTaskRead]


class ProcurementStateResponse(BaseModel):
    request_id: uuid.UUID
    purchase_status: str
    version: int
    idempotent_replay: bool = False


class ProcurementVersionRequest(BaseModel):
    version: int = Field(ge=0)


class ApprovalDecisionResponse(BaseModel):
    task_id: uuid.UUID
    task_status: TaskStatus
    purchase_status: str
    decision_id: uuid.UUID
    workflow_run_id: uuid.UUID
    next_task_id: uuid.UUID | None
    idempotent_replay: bool = False
