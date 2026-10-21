import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]


class PurchaseIntent(BaseModel):
    category: str | None = Field(default=None, max_length=100)
    item_description: str | None = Field(default=None, max_length=500)
    quantity: int | None = Field(default=None, gt=0, le=100_000)
    unit_price_limit: PositiveMoney | None = None
    total_budget: PositiveMoney | None = None
    purpose: str | None = Field(default=None, max_length=500)
    priority: Literal["LOW", "NORMAL", "HIGH"] = "NORMAL"
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("category", "item_description", "purpose", "notes", mode="before")
    @classmethod
    def empty_strings_are_missing(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("unit_price_limit", "total_budget")
    @classmethod
    def normalize_money(cls, value: Decimal | None) -> Decimal | None:
        return value.quantize(Decimal("0.01")) if value is not None else None

    @model_validator(mode="after")
    def calculate_total_budget(self) -> "PurchaseIntent":
        if self.total_budget is None and self.quantity and self.unit_price_limit:
            self.total_budget = (self.unit_price_limit * self.quantity).quantize(Decimal("0.01"))
        return self


class IntentParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    session_id: uuid.UUID | None = None


class IntentParseResponse(BaseModel):
    intent: PurchaseIntent
    missing_fields: list[str]
    follow_up_question: str | None
    requires_confirmation: bool = True
    source: Literal["MOCK", "OPENAI_COMPATIBLE"]


class ChatSessionCreate(BaseModel):
    title: str = Field(default="新的采购对话", min_length=1, max_length=120)


class ChatSessionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    archived: bool | None = None


class ChatSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    title: str
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message cannot be blank")
        return value


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    sender: Literal["USER", "ASSISTANT"]
    content: str
    status: Literal["COMPLETED", "FAILED", "CONFIRMED"]
    run_id: uuid.UUID | None
    payload_json: dict[str, Any] | None
    created_at: datetime


class ChatTurnResponse(BaseModel):
    run_id: uuid.UUID
    user_message: ChatMessageRead
    assistant_message: ChatMessageRead
    parse_result: IntentParseResponse


class IntentConfirmationRequest(BaseModel):
    intent: PurchaseIntent


class IntentConfirmationResponse(BaseModel):
    message: ChatMessageRead
    confirmed_intent: PurchaseIntent
    purchase_request_created: bool
    purchase_request_id: uuid.UUID
