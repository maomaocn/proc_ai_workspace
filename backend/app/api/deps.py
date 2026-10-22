from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.identity import User

bearer_scheme = HTTPBearer(auto_error=False)
DatabaseSession = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: DatabaseSession,
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(401, "UNAUTHORIZED", "需要登录后访问")

    user_id = decode_access_token(credentials.credentials)
    query = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.role_assignments), selectinload(User.department))
    )
    user = await session.scalar(query)
    if user is None or not user.is_active:
        raise AppError(401, "UNAUTHORIZED", "登录状态无效或已过期")
    request.state.actor_id = str(user.id)
    request.state.actor_roles = sorted(user.roles)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*required_roles: str) -> Callable[..., Coroutine[Any, Any, User]]:
    async def role_dependency(user: CurrentUser) -> User:
        if user.roles.isdisjoint(required_roles):
            raise AppError(403, "FORBIDDEN", "无权执行此操作")
        return user

    return role_dependency
