import hashlib
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DatabaseSession
from app.core.config import settings
from app.core.errors import AppError
from app.models.knowledge import KnowledgeACL, KnowledgeCollection, KnowledgeDocument
from app.rag.loader import validate_file
from app.rag.permissions import (
    accessible_collection_query,
    collection_permission,
    require_collection_permission,
)
from app.rag.service import knowledge_service
from app.schemas.common import Page
from app.schemas.knowledge import (
    CollectionCreate,
    CollectionRead,
    DocumentDetail,
    DocumentRead,
    SearchRequest,
    SearchResponse,
)

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])


@router.get("/collections", response_model=list[CollectionRead])
async def list_collections(
    user: CurrentUser,
    session: DatabaseSession,
) -> list[CollectionRead]:
    collections = list((await session.scalars(accessible_collection_query(user))).all())
    results: list[CollectionRead] = []
    for collection in collections:
        _, permission = await collection_permission(session, user, collection.id)
        document_count = (
            await session.scalar(
                select(func.count())
                .select_from(KnowledgeDocument)
                .where(
                    KnowledgeDocument.collection_id == collection.id,
                    KnowledgeDocument.status != "DELETED",
                )
            )
            or 0
        )
        results.append(
            CollectionRead(
                id=collection.id,
                name=collection.name,
                visibility=collection.visibility,
                effective_permission=permission,
                document_count=document_count,
                created_at=collection.created_at,
                updated_at=collection.updated_at,
            )
        )
    return results


@router.post("/collections", response_model=CollectionRead, status_code=201)
async def create_collection(
    body: CollectionCreate,
    user: CurrentUser,
    session: DatabaseSession,
) -> CollectionRead:
    if "ADMIN" not in user.roles:
        raise AppError(403, "FORBIDDEN", "仅管理员可以创建知识库")
    collection = KnowledgeCollection(
        name=body.name,
        visibility=body.visibility,
        created_by=user.id,
        acl_entries=[
            KnowledgeACL(principal_type="ROLE", principal_id=role, permission="READ")
            for role in sorted(set(body.readable_by_roles) - {"ADMIN"})
        ],
    )
    session.add(collection)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, "STATE_CONFLICT", "同名知识库已存在") from exc
    await session.refresh(collection)
    return CollectionRead(
        id=collection.id,
        name=collection.name,
        visibility=collection.visibility,
        effective_permission="ADMIN",
        document_count=0,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


@router.get("/documents", response_model=Page[DocumentRead])
async def list_documents(
    user: CurrentUser,
    session: DatabaseSession,
    collection_id: uuid.UUID,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[DocumentRead]:
    await require_collection_permission(session, user, collection_id, "READ")
    filters = (
        KnowledgeDocument.collection_id == collection_id,
        KnowledgeDocument.status != "DELETED",
    )
    total = (
        await session.scalar(select(func.count()).select_from(KnowledgeDocument).where(*filters))
        or 0
    )
    documents = list(
        (
            await session.scalars(
                select(KnowledgeDocument)
                .where(*filters)
                .options(
                    selectinload(KnowledgeDocument.uploader),
                    selectinload(KnowledgeDocument.chunks),
                )
                .order_by(KnowledgeDocument.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return Page(
        items=[_document_read(document) for document in documents],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/documents", response_model=DocumentRead, status_code=201)
async def upload_document(
    user: CurrentUser,
    session: DatabaseSession,
    collection_id: Annotated[uuid.UUID, Form()],
    file: Annotated[UploadFile, File()],
) -> DocumentRead:
    await require_collection_permission(session, user, collection_id, "WRITE")
    content = await file.read(settings.knowledge_max_file_bytes + 1)
    filename, mime_type = validate_file(
        file.filename,
        file.content_type,
        content,
        settings.knowledge_max_file_bytes,
    )
    digest = hashlib.sha256(content).hexdigest()
    duplicate = await session.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.collection_id == collection_id,
            KnowledgeDocument.sha256 == digest,
            KnowledgeDocument.status != "DELETED",
        )
    )
    if duplicate is not None:
        raise AppError(
            409,
            "STATE_CONFLICT",
            "相同内容的文档已存在",
            {"document_id": str(duplicate.id)},
        )

    document_id = uuid.uuid4()
    upload_dir = Path(settings.knowledge_upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    storage_path = upload_dir / f"{document_id}{Path(filename).suffix.lower()}"
    try:
        storage_path.write_bytes(content)
    except OSError as exc:
        raise AppError(503, "TOOL_UNAVAILABLE", "文档存储不可用") from exc

    document = KnowledgeDocument(
        id=document_id,
        collection_id=collection_id,
        filename=filename,
        sha256=digest,
        mime_type=mime_type,
        size_bytes=len(content),
        storage_path=str(storage_path.resolve()),
        status="PENDING",
        uploaded_by=user.id,
        index_version=1,
    )
    session.add(document)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        storage_path.unlink(missing_ok=True)
        raise AppError(409, "STATE_CONFLICT", "相同内容的文档已存在") from exc
    indexed = await knowledge_service.index_document(session, document.id)
    return _document_read(indexed)


@router.get("/documents/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: uuid.UUID,
    user: CurrentUser,
    session: DatabaseSession,
) -> DocumentDetail:
    document = await knowledge_service.get_document(session, document_id)
    if document.status == "DELETED":
        raise AppError(404, "NOT_FOUND", "文档不存在")
    await require_collection_permission(session, user, document.collection_id, "READ")
    base = _document_read(document)
    return DocumentDetail(**base.model_dump(), chunks=document.chunks)


@router.post("/documents/{document_id}/reindex", response_model=DocumentRead)
async def reindex_document(
    document_id: uuid.UUID,
    user: CurrentUser,
    session: DatabaseSession,
) -> DocumentRead:
    document = await knowledge_service.get_document(session, document_id)
    await require_collection_permission(session, user, document.collection_id, "ADMIN")
    indexed = await knowledge_service.reindex_document(session, document)
    return _document_read(indexed)


@router.delete("/documents/{document_id}", response_model=DocumentRead)
async def delete_document(
    document_id: uuid.UUID,
    user: CurrentUser,
    session: DatabaseSession,
) -> DocumentRead:
    document = await knowledge_service.get_document(session, document_id)
    await require_collection_permission(session, user, document.collection_id, "ADMIN")
    if document.status == "DELETED":
        raise AppError(404, "NOT_FOUND", "文档不存在")
    deleted = await knowledge_service.delete_document(session, document)
    return _document_read(deleted)


@router.post("/search", response_model=SearchResponse)
async def search_knowledge(
    body: SearchRequest,
    user: CurrentUser,
    session: DatabaseSession,
) -> SearchResponse:
    await require_collection_permission(session, user, body.collection_id, "READ")
    return await knowledge_service.search(session, body.collection_id, body.query, body.top_k)


def _document_read(document: KnowledgeDocument) -> DocumentRead:
    return DocumentRead(
        id=document.id,
        collection_id=document.collection_id,
        filename=document.filename,
        sha256=document.sha256,
        mime_type=document.mime_type,
        size_bytes=document.size_bytes,
        status=document.status,
        uploaded_by=document.uploaded_by,
        uploader=document.uploader,
        index_version=document.index_version,
        error_code=document.error_code,
        chunk_count=len(document.chunks),
        created_at=document.created_at,
        updated_at=document.updated_at,
    )
