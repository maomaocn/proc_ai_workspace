import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import DatabaseSession, require_roles
from app.core.errors import AppError
from app.models.identity import User
from app.models.procurement import InventoryItem, Supplier, SupplierQuote
from app.schemas.common import Page
from app.schemas.procurement import (
    SupplierCreate,
    SupplierQuoteCreate,
    SupplierQuoteRead,
    SupplierRead,
    SupplierUpdate,
)

router = APIRouter(tags=["Suppliers"])
SupplierManager = Annotated[User, Depends(require_roles("PROCUREMENT", "ADMIN"))]


@router.get("/suppliers", response_model=Page[SupplierRead])
async def list_suppliers(
    _: SupplierManager,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[SupplierRead]:
    total = await session.scalar(select(func.count()).select_from(Supplier)) or 0
    items = list(
        (
            await session.scalars(
                select(Supplier)
                .order_by(Supplier.name)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return Page(items=items, page=page, page_size=page_size, total=total)


@router.post("/suppliers", response_model=SupplierRead, status_code=201)
async def create_supplier(
    body: SupplierCreate, _: SupplierManager, session: DatabaseSession
) -> Supplier:
    supplier = Supplier(name=body.name, active=body.active, demo_data=True)
    session.add(supplier)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, "STATE_CONFLICT", "供应商名称已存在") from exc
    await session.refresh(supplier)
    return supplier


@router.patch("/suppliers/{supplier_id}", response_model=SupplierRead)
async def update_supplier(
    supplier_id: uuid.UUID,
    body: SupplierUpdate,
    _: SupplierManager,
    session: DatabaseSession,
) -> Supplier:
    supplier = await session.get(Supplier, supplier_id)
    if supplier is None:
        raise AppError(404, "NOT_FOUND", "供应商不存在")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, "STATE_CONFLICT", "供应商名称已存在") from exc
    await session.refresh(supplier)
    return supplier


@router.get("/supplier-quotes", response_model=Page[SupplierQuoteRead])
async def list_supplier_quotes(
    _: SupplierManager,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    supplier_id: uuid.UUID | None = None,
    inventory_item_id: uuid.UUID | None = None,
) -> Page[SupplierQuoteRead]:
    filters = []
    if supplier_id:
        filters.append(SupplierQuote.supplier_id == supplier_id)
    if inventory_item_id:
        filters.append(SupplierQuote.inventory_item_id == inventory_item_id)
    total = await session.scalar(
        select(func.count()).select_from(SupplierQuote).where(*filters)
    ) or 0
    items = list(
        (
            await session.scalars(
                select(SupplierQuote)
                .where(*filters)
                .options(
                    selectinload(SupplierQuote.supplier),
                    selectinload(SupplierQuote.inventory_item),
                )
                .order_by(SupplierQuote.quoted_at.desc(), SupplierQuote.unit_price)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return Page(items=items, page=page, page_size=page_size, total=total)


@router.post("/supplier-quotes", response_model=SupplierQuoteRead, status_code=201)
async def create_supplier_quote(
    body: SupplierQuoteCreate, _: SupplierManager, session: DatabaseSession
) -> SupplierQuote:
    supplier = await session.get(Supplier, body.supplier_id)
    item = await session.get(InventoryItem, body.inventory_item_id)
    if supplier is None or item is None:
        raise AppError(404, "NOT_FOUND", "供应商或库存商品不存在")
    if not supplier.active or not item.active:
        raise AppError(422, "BUSINESS_RULE_VIOLATION", "停用资源不能新增报价")
    quote = SupplierQuote(
        **body.model_dump(),
        currency="CNY",
        source_type="DEMO",
    )
    session.add(quote)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, "STATE_CONFLICT", "相同时间的演示报价已存在") from exc
    return await session.scalar(
        select(SupplierQuote)
        .where(SupplierQuote.id == quote.id)
        .options(
            selectinload(SupplierQuote.supplier),
            selectinload(SupplierQuote.inventory_item),
        )
    )
