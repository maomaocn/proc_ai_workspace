from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.identity import User


class KnowledgeCollection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_collections"
    __table_args__ = (
        CheckConstraint(
            "char_length(name) BETWEEN 1 AND 120", name="ck_knowledge_collections_name"
        ),
        CheckConstraint(
            "visibility IN ('PRIVATE', 'INTERNAL')",
            name="ck_knowledge_collections_visibility",
        ),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="PRIVATE")
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    creator: Mapped[User] = relationship(foreign_keys=[created_by])
    acl_entries: Mapped[list[KnowledgeACL]] = relationship(
        back_populates="collection", cascade="all, delete-orphan"
    )
    documents: Mapped[list[KnowledgeDocument]] = relationship(back_populates="collection")


class KnowledgeACL(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_acl"
    __table_args__ = (
        UniqueConstraint(
            "collection_id",
            "principal_type",
            "principal_id",
            "permission",
            name="uq_knowledge_acl_grant",
        ),
        CheckConstraint(
            "principal_type IN ('USER', 'ROLE')", name="ck_knowledge_acl_principal_type"
        ),
        CheckConstraint(
            "permission IN ('READ', 'WRITE', 'ADMIN')", name="ck_knowledge_acl_permission"
        ),
        CheckConstraint("char_length(principal_id) > 0", name="ck_knowledge_acl_principal_id"),
    )

    collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_collections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    principal_type: Mapped[str] = mapped_column(String(16), nullable=False)
    principal_id: Mapped[str] = mapped_column(String(64), nullable=False)
    permission: Mapped[str] = mapped_column(String(16), nullable=False)

    collection: Mapped[KnowledgeCollection] = relationship(back_populates="acl_entries")


class KnowledgeDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_knowledge_documents_size"),
        CheckConstraint(
            "status IN ('PENDING', 'INDEXING', 'READY', 'FAILED', 'DELETED')",
            name="ck_knowledge_documents_status",
        ),
        CheckConstraint("index_version >= 1", name="ck_knowledge_documents_index_version"),
        Index(
            "uq_knowledge_documents_active_sha",
            "collection_id",
            "sha256",
            unique=True,
            postgresql_where=text("status <> 'DELETED'"),
        ),
    )

    collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_collections.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING", index=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    index_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    collection: Mapped[KnowledgeCollection] = relationship(back_populates="documents")
    uploader: Mapped[User] = relationship(foreign_keys=[uploaded_by])
    chunks: Mapped[list[KnowledgeChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="KnowledgeChunk.chunk_index",
    )


class KnowledgeChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_knowledge_chunks_document_index"),
        UniqueConstraint("vector_id", name="uq_knowledge_chunks_vector_id"),
        CheckConstraint("chunk_index >= 0", name="ck_knowledge_chunks_index"),
        CheckConstraint("char_length(content) > 0", name="ck_knowledge_chunks_content"),
        CheckConstraint(
            "page_number IS NULL OR page_number >= 1", name="ck_knowledge_chunks_page_number"
        ),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vector_id: Mapped[str] = mapped_column(String(64), nullable=False)

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")
