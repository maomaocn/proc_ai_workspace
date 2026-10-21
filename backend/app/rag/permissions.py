import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.identity import User
from app.models.knowledge import KnowledgeACL, KnowledgeCollection

PERMISSION_RANK = {"READ": 1, "WRITE": 2, "ADMIN": 3}


async def collection_permission(
    session: AsyncSession,
    user: User,
    collection_id: uuid.UUID,
) -> tuple[KnowledgeCollection, str]:
    collection = await session.get(KnowledgeCollection, collection_id)
    if collection is None:
        raise AppError(404, "NOT_FOUND", "知识库不存在")
    if "ADMIN" in user.roles:
        return collection, "ADMIN"

    conditions = [
        (KnowledgeACL.principal_type == "USER") & (KnowledgeACL.principal_id == str(user.id))
    ]
    if user.roles:
        conditions.append(
            (KnowledgeACL.principal_type == "ROLE")
            & (KnowledgeACL.principal_id.in_(sorted(user.roles)))
        )
    permissions = list(
        (
            await session.scalars(
                select(KnowledgeACL.permission).where(
                    KnowledgeACL.collection_id == collection_id,
                    or_(*conditions),
                )
            )
        ).all()
    )
    if not permissions:
        raise AppError(403, "FORBIDDEN", "无权访问此知识库")
    effective = max(permissions, key=PERMISSION_RANK.__getitem__)
    return collection, effective


async def require_collection_permission(
    session: AsyncSession,
    user: User,
    collection_id: uuid.UUID,
    minimum: str,
) -> tuple[KnowledgeCollection, str]:
    collection, permission = await collection_permission(session, user, collection_id)
    if PERMISSION_RANK[permission] < PERMISSION_RANK[minimum]:
        raise AppError(403, "FORBIDDEN", "无权执行此知识库操作")
    return collection, permission


def accessible_collection_query(user: User):
    query = select(KnowledgeCollection)
    if "ADMIN" in user.roles:
        return query.order_by(KnowledgeCollection.name)
    role_condition = (
        (KnowledgeACL.principal_type == "ROLE")
        & (KnowledgeACL.principal_id.in_(sorted(user.roles)))
        if user.roles
        else False
    )
    return (
        query.join(KnowledgeACL)
        .where(
            or_(
                (KnowledgeACL.principal_type == "USER")
                & (KnowledgeACL.principal_id == str(user.id)),
                role_condition,
            )
        )
        .distinct()
        .order_by(KnowledgeCollection.name)
    )
