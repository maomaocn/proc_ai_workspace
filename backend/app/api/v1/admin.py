from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import DatabaseSession, require_roles
from app.core.errors import AppError
from app.core.security import hash_password
from app.models.identity import Department, User, UserRole
from app.schemas.auth import UserCreate, UserRead
from app.schemas.common import Page

router = APIRouter(prefix="/admin", tags=["Administration"])
AdminUser = Annotated[User, Depends(require_roles("ADMIN"))]


@router.get("/users", response_model=Page[UserRead])
async def list_users(
    _: AdminUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[UserRead]:
    total = await session.scalar(select(func.count()).select_from(User)) or 0
    query = (
        select(User)
        .options(selectinload(User.role_assignments), selectinload(User.department))
        .order_by(User.username)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    users = list((await session.scalars(query)).all())
    return Page(
        items=[UserRead.model_validate(user) for user in users],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/users", response_model=UserRead, status_code=201)
async def create_user(
    body: UserCreate,
    _: AdminUser,
    session: DatabaseSession,
) -> UserRead:
    department = await session.get(Department, body.department_id)
    if department is None:
        raise AppError(400, "VALIDATION_ERROR", "指定的部门不存在")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        department=department,
        role_assignments=[UserRole(role=role) for role in sorted(body.roles)],
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, "STATE_CONFLICT", "用户名已存在") from exc

    query = (
        select(User)
        .where(User.id == user.id)
        .options(selectinload(User.role_assignments), selectinload(User.department))
    )
    created = await session.scalar(query)
    if created is None:
        raise AppError(500, "INTERNAL_ERROR", "用户创建结果无法读取")
    return UserRead.model_validate(created)
