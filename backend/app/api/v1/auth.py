from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DatabaseSession
from app.core.errors import AppError
from app.core.security import create_access_token, verify_password_or_dummy
from app.models.identity import User
from app.schemas.auth import LoginRequest, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: DatabaseSession) -> TokenResponse:
    query = (
        select(User)
        .where(User.username == body.username.strip())
        .options(selectinload(User.role_assignments), selectinload(User.department))
    )
    user = await session.scalar(query)
    password_valid = verify_password_or_dummy(
        body.password, user.password_hash if user is not None else None
    )
    if user is None or not password_valid or not user.is_active:
        raise AppError(401, "UNAUTHORIZED", "用户名或密码错误")

    token, expires_at = create_access_token(user.id, user.roles)
    return TokenResponse(
        access_token=token,
        expires_at=expires_at,
        user=UserRead.model_validate(user),
    )


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
