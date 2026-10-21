"""Add M2 knowledge base, ACL, document, and chunk tables.

Revision ID: 20261021_0003
Revises: 20261021_0002
Create Date: 2026-10-21 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261021_0003"
down_revision: str | Sequence[str] | None = "20261021_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "knowledge_collections",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("visibility", sa.String(length=16), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 120", name="ck_knowledge_collections_name"
        ),
        sa.CheckConstraint(
            "visibility IN ('PRIVATE', 'INTERNAL')",
            name="ck_knowledge_collections_visibility",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        op.f("ix_knowledge_collections_created_by"),
        "knowledge_collections",
        ["created_by"],
    )
    op.create_table(
        "knowledge_acl",
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("principal_type", sa.String(length=16), nullable=False),
        sa.Column("principal_id", sa.String(length=64), nullable=False),
        sa.Column("permission", sa.String(length=16), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "principal_type IN ('USER', 'ROLE')", name="ck_knowledge_acl_principal_type"
        ),
        sa.CheckConstraint(
            "permission IN ('READ', 'WRITE', 'ADMIN')", name="ck_knowledge_acl_permission"
        ),
        sa.CheckConstraint("char_length(principal_id) > 0", name="ck_knowledge_acl_principal_id"),
        sa.ForeignKeyConstraint(
            ["collection_id"], ["knowledge_collections.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "collection_id",
            "principal_type",
            "principal_id",
            "permission",
            name="uq_knowledge_acl_grant",
        ),
    )
    op.create_index(op.f("ix_knowledge_acl_collection_id"), "knowledge_acl", ["collection_id"])
    op.create_table(
        "knowledge_documents",
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("index_version", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint("size_bytes > 0", name="ck_knowledge_documents_size"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'INDEXING', 'READY', 'FAILED', 'DELETED')",
            name="ck_knowledge_documents_status",
        ),
        sa.CheckConstraint("index_version >= 1", name="ck_knowledge_documents_index_version"),
        sa.ForeignKeyConstraint(
            ["collection_id"], ["knowledge_collections.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_knowledge_documents_collection_id"),
        "knowledge_documents",
        ["collection_id"],
    )
    op.create_index(op.f("ix_knowledge_documents_status"), "knowledge_documents", ["status"])
    op.create_index(
        op.f("ix_knowledge_documents_uploaded_by"),
        "knowledge_documents",
        ["uploaded_by"],
    )
    op.create_index(
        "uq_knowledge_documents_active_sha",
        "knowledge_documents",
        ["collection_id", "sha256"],
        unique=True,
        postgresql_where=sa.text("status <> 'DELETED'"),
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("vector_id", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint("chunk_index >= 0", name="ck_knowledge_chunks_index"),
        sa.CheckConstraint("char_length(content) > 0", name="ck_knowledge_chunks_content"),
        sa.CheckConstraint(
            "page_number IS NULL OR page_number >= 1", name="ck_knowledge_chunks_page_number"
        ),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id", "chunk_index", name="uq_knowledge_chunks_document_index"
        ),
        sa.UniqueConstraint("vector_id", name="uq_knowledge_chunks_vector_id"),
    )
    op.create_index(op.f("ix_knowledge_chunks_document_id"), "knowledge_chunks", ["document_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_knowledge_chunks_document_id"), table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index("uq_knowledge_documents_active_sha", table_name="knowledge_documents")
    op.drop_index(op.f("ix_knowledge_documents_uploaded_by"), table_name="knowledge_documents")
    op.drop_index(op.f("ix_knowledge_documents_status"), table_name="knowledge_documents")
    op.drop_index(op.f("ix_knowledge_documents_collection_id"), table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
    op.drop_index(op.f("ix_knowledge_acl_collection_id"), table_name="knowledge_acl")
    op.drop_table("knowledge_acl")
    op.drop_index(op.f("ix_knowledge_collections_created_by"), table_name="knowledge_collections")
    op.drop_table("knowledge_collections")
