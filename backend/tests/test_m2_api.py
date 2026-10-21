import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.seed import DEMO_PASSWORD, seed_demo_data
from app.db.session import engine, get_session
from app.main import app
from app.rag.vector_store import get_vector_store

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS", "false").lower() != "true",
    reason="set RUN_DB_TESTS=true to run PostgreSQL integration tests",
)

SAMPLE_POLICY = """# 企业采购管理制度（Mock 演示）

办公笔记本电脑单台预算原则上不超过 6000 元。采购前应优先核对可用库存。

采购总金额不超过 10000 元时，由部门负责人进行一级审批。采购总金额超过 10000 元时，
必须依次完成部门负责人审批和财务审批。审批规则缺失时不得自动提交。

申请人不得审批本人提交的采购申请。所有操作必须记录审计事件。
"""


@pytest_asyncio.fixture
async def client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    await seed_demo_data()
    old_upload_dir = settings.knowledge_upload_dir
    old_chroma_path = settings.chroma_path
    old_collection_name = settings.chroma_collection_name
    settings.knowledge_upload_dir = str(tmp_path / "uploads")
    settings.chroma_path = str(tmp_path / "chroma")
    settings.chroma_collection_name = f"test-{uuid.uuid4().hex}"
    get_vector_store.cache_clear()

    async with engine.connect() as connection:
        transaction = await connection.begin()
        db_session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async def override_session() -> AsyncIterator[AsyncSession]:
            yield db_session

        app.dependency_overrides[get_session] = override_session
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as test_client:
            yield test_client
        app.dependency_overrides.clear()
        await db_session.close()
        await transaction.rollback()

    get_vector_store.cache_clear()
    settings.knowledge_upload_dir = old_upload_dir
    settings.chroma_path = old_chroma_path
    settings.chroma_collection_name = old_collection_name


async def login(client: httpx.AsyncClient, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def sample_policy() -> bytes:
    return SAMPLE_POLICY.encode()


@pytest.mark.asyncio
async def test_upload_search_acl_duplicate_and_delete_flow(client: httpx.AsyncClient) -> None:
    admin = await login(client, "admin")
    employee = await login(client, "employee")
    techadmin = await login(client, "techadmin")

    admin_collections = await client.get("/api/v1/knowledge/collections", headers=headers(admin))
    assert admin_collections.status_code == 200
    collection = next(item for item in admin_collections.json() if item["name"] == "企业采购制度")
    collection_id = collection["id"]

    employee_collections = await client.get(
        "/api/v1/knowledge/collections", headers=headers(employee)
    )
    assert collection_id in {item["id"] for item in employee_collections.json()}
    tech_collections = await client.get("/api/v1/knowledge/collections", headers=headers(techadmin))
    assert collection_id not in {item["id"] for item in tech_collections.json()}

    upload = await client.post(
        "/api/v1/knowledge/documents",
        headers=headers(admin),
        data={"collection_id": collection_id},
        files={"file": ("采购管理制度.md", sample_policy(), "text/markdown")},
    )
    assert upload.status_code == 201, upload.text
    document = upload.json()
    assert document["status"] == "READY"
    assert document["chunk_count"] >= 1
    document_id = document["id"]

    duplicate = await client.post(
        "/api/v1/knowledge/documents",
        headers=headers(admin),
        data={"collection_id": collection_id},
        files={"file": ("duplicate.md", sample_policy(), "text/markdown")},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "STATE_CONFLICT"

    employee_upload = await client.post(
        "/api/v1/knowledge/documents",
        headers=headers(employee),
        data={"collection_id": collection_id},
        files={"file": ("employee.md", b"employee content", "text/markdown")},
    )
    assert employee_upload.status_code == 403

    search = await client.post(
        "/api/v1/knowledge/search",
        headers=headers(employee),
        json={"collection_id": collection_id, "query": "笔记本超过一万元如何审批", "top_k": 5},
    )
    assert search.status_code == 200, search.text
    result = search.json()
    assert result["has_sufficient_evidence"] is True
    assert result["source"] == "MOCK"
    assert result["hits"][0]["document_id"] == document_id
    assert result["hits"][0]["filename"] == "采购管理制度.md"
    assert result["hits"][0]["page_number"] == 1
    assert "超过 10000 元" in result["answer"]

    reindexed = await client.post(
        f"/api/v1/knowledge/documents/{document_id}/reindex", headers=headers(admin)
    )
    assert reindexed.status_code == 200, reindexed.text
    assert reindexed.json()["status"] == "READY"
    assert reindexed.json()["index_version"] == 2

    no_evidence = await client.post(
        "/api/v1/knowledge/search",
        headers=headers(employee),
        json={"collection_id": collection_id, "query": "火星土壤采样器", "top_k": 5},
    )
    assert no_evidence.status_code == 200
    assert no_evidence.json()["hits"] == []
    assert no_evidence.json()["has_sufficient_evidence"] is False
    assert no_evidence.json()["answer"] == "当前知识库未检索到足够依据。"

    deleted = await client.delete(
        f"/api/v1/knowledge/documents/{document_id}", headers=headers(admin)
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["status"] == "DELETED"

    after_delete = await client.post(
        "/api/v1/knowledge/search",
        headers=headers(employee),
        json={"collection_id": collection_id, "query": "笔记本审批额度", "top_k": 5},
    )
    assert after_delete.status_code == 200
    assert after_delete.json()["hits"] == []


@pytest.mark.asyncio
async def test_private_collection_does_not_leak_name_or_content(client: httpx.AsyncClient) -> None:
    admin = await login(client, "admin")
    employee = await login(client, "employee")

    created = await client.post(
        "/api/v1/knowledge/collections",
        headers=headers(admin),
        json={"name": f"私有制度-{uuid.uuid4().hex[:8]}", "visibility": "PRIVATE"},
    )
    assert created.status_code == 201
    private_id = created.json()["id"]

    employee_collections = await client.get(
        "/api/v1/knowledge/collections", headers=headers(employee)
    )
    assert private_id not in {item["id"] for item in employee_collections.json()}

    forbidden = await client.post(
        "/api/v1/knowledge/search",
        headers=headers(employee),
        json={"collection_id": private_id, "query": "私有制度内容", "top_k": 5},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_upload_rejects_unsupported_extension(client: httpx.AsyncClient) -> None:
    admin = await login(client, "admin")
    collections = await client.get("/api/v1/knowledge/collections", headers=headers(admin))
    collection_id = collections.json()[0]["id"]

    response = await client.post(
        "/api/v1/knowledge/documents",
        headers=headers(admin),
        data={"collection_id": collection_id},
        files={"file": ("malware.exe", b"unsafe", "application/octet-stream")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
