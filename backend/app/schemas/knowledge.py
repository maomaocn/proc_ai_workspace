import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

KnowledgePermission = Literal["READ", "WRITE", "ADMIN"]
DocumentStatus = Literal["PENDING", "INDEXING", "READY", "FAILED", "DELETED"]


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    visibility: Literal["PRIVATE", "INTERNAL"] = "PRIVATE"
    readable_by_roles: list[
        Literal["EMPLOYEE", "APPROVER", "PROCUREMENT", "ADMIN", "TECH_ADMIN"]
    ] = Field(default_factory=list, max_length=5)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.split())


class CollectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    visibility: str
    effective_permission: KnowledgePermission
    document_count: int = 0
    created_at: datetime
    updated_at: datetime


class UploaderSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    collection_id: uuid.UUID
    filename: str
    sha256: str
    mime_type: str
    size_bytes: int
    status: DocumentStatus
    uploaded_by: uuid.UUID
    uploader: UploaderSummary
    index_version: int
    error_code: str | None
    chunk_count: int = 0
    created_at: datetime
    updated_at: datetime


class ChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chunk_index: int
    content: str
    page_number: int | None


class DocumentDetail(DocumentRead):
    chunks: list[ChunkRead]


class SearchRequest(BaseModel):
    collection_id: uuid.UUID
    query: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        return " ".join(value.split())


class SearchHit(BaseModel):
    document_id: uuid.UUID
    filename: str
    chunk_id: uuid.UUID
    page_number: int | None
    snippet: str
    score: float = Field(ge=0.0, le=1.0)


class SearchResponse(BaseModel):
    hits: list[SearchHit]
    answer: str
    source: Literal["MOCK", "REMOTE"]
    has_sufficient_evidence: bool
