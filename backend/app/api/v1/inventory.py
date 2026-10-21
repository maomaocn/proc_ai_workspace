import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DatabaseSession, require_roles
from app.core.errors import AppError
from app.models.identity import User
from app.models.procurement import InventoryItem
from app.schemas.common import Page
from app.schemas.procurement import InventoryItemCreate, InventoryItemRead, InventoryItemUpdate

router = APIRouter(prefix="/inventory/items", tags=["Inventory"])
AdminUser = Annotated[User, Depends(require_roles("ADMIN"))]


@router.get("", response_model=Page[InventoryItemRead])
async def list_inventory(
    _: CurrentUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    query: Annotated[str | None, Query(max_length=100)] = None,
    category: Annotated[str | None, Query(max_length=100)] = None,
    active: bool | None = None,
) -> Page[InventoryItemRead]:
    filters = []
    if query:
        pattern = f"%{query.strip()}%"
        filters.append(or_(InventoryItem.sku.ilike(pattern), InventoryItem.model.ilike(pattern)))
    if category:
        filters.append(InventoryItem.category == category.strip())
    if active is not None:
        filters.append(InventoryItem.active.is_(active))
    total = await session.scalar(
        select(func.count()).select_from(InventoryItem).where(*filters)
    ) or 0
    items = list(
        (
            await session.scalars(
                select(InventoryItem)
                .where(*filters)
                .order_by(InventoryItem.category, InventoryItem.sku)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return Page(items=items, page=page, page_size=page_size, total=total)


@router.post("", response_model=InventoryItemRead, status_code=201)
async def create_inventory_item(
    body: InventoryItemCreate, _: AdminUser, session: DatabaseSession
) -> InventoryItem:
    item = InventoryItem(**body.model_dump())
    session.add(item)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, "STATE_CONFLICT", "SKU 已存在") from exc
    await session.refresh(item)
    return item


@router.patch("/{item_id}", response_model=InventoryItemRead)
async def update_inventory_item(
    item_id: uuid.UUID,
    body: InventoryItemUpdate,
    _: AdminUser,
    session: DatabaseSession,
) -> InventoryItem:
    item = await session.get(InventoryItem, item_id)
    if item is None:
        raise AppError(404, "NOT_FOUND", "库存商品不存在")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await session.commit()
    await session.refresh(item)
    return item
