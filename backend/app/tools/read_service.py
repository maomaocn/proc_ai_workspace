from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.procurement import InventoryItem, SupplierQuote
from app.tools.schemas import (
    InventorySearchInput,
    InventoryToolItem,
    QuoteToolItem,
    SupplierQuoteInput,
)


async def query_inventory(
    session: AsyncSession, parameters: InventorySearchInput
) -> dict[str, Any]:
    limit = min(parameters.limit, settings.tool_max_result_items)
    rows = list(
        (
            await session.scalars(
                select(InventoryItem)
                .where(
                    InventoryItem.active.is_(True),
                    InventoryItem.category.ilike(f"%{parameters.category}%"),
                    InventoryItem.available_qty >= parameters.min_qty,
                )
                .order_by(InventoryItem.reference_price, InventoryItem.sku)
                .limit(limit)
            )
        ).all()
    )
    return {
        "source": "DATABASE",
        "items": [
            InventoryToolItem.model_validate(row, from_attributes=True).model_dump(mode="json")
            for row in rows
        ],
    }


async def query_supplier_quotes(
    session: AsyncSession, parameters: SupplierQuoteInput
) -> dict[str, Any]:
    limit = min(parameters.limit, settings.tool_max_result_items)
    rows = list(
        (
            await session.scalars(
                select(SupplierQuote)
                .where(SupplierQuote.inventory_item_id == parameters.item_id)
                .options(
                    selectinload(SupplierQuote.supplier),
                    selectinload(SupplierQuote.inventory_item),
                )
                .order_by(SupplierQuote.unit_price, SupplierQuote.quoted_at.desc())
                .limit(limit)
            )
        ).all()
    )
    quotes: list[dict[str, Any]] = []
    for row in rows:
        if not row.supplier.active or not row.inventory_item.active:
            continue
        total = (row.unit_price * parameters.quantity).quantize(Decimal("0.01"))
        quotes.append(
            QuoteToolItem(
                quote_id=row.id,
                supplier_id=row.supplier_id,
                supplier_name=row.supplier.name,
                item_id=row.inventory_item_id,
                item_model=row.inventory_item.model,
                available_qty=row.inventory_item.available_qty,
                unit_price=row.unit_price,
                quantity=parameters.quantity,
                total_price=total,
                currency=row.currency,
                quoted_at=row.quoted_at.isoformat(),
                source_type=row.source_type,
            ).model_dump(mode="json")
        )
    return {"source": "DATABASE", "quotes": quotes}
