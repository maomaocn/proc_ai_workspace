import uuid
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class InventorySearchInput(BaseModel):
    category: str = Field(min_length=1, max_length=100)
    min_qty: int = Field(default=1, ge=0, le=1_000_000)
    limit: int = Field(default=20, ge=1, le=50)

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str) -> str:
        return " ".join(value.split())


class SupplierQuoteInput(BaseModel):
    item_id: uuid.UUID
    quantity: int = Field(gt=0, le=100_000)
    limit: int = Field(default=20, ge=1, le=50)


class PolicySearchInput(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    collection_id: uuid.UUID | None = None
    top_k: int = Field(default=3, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        return " ".join(value.split())


class InventoryToolItem(BaseModel):
    id: uuid.UUID
    sku: str
    category: str
    model: str
    available_qty: int
    reference_price: Decimal


class QuoteToolItem(BaseModel):
    quote_id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    item_id: uuid.UUID
    item_model: str
    available_qty: int
    unit_price: Decimal
    quantity: int
    total_price: Decimal
    currency: str
    quoted_at: str
    source_type: str
