import uuid
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import AppError
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.rag.chunker import chunk_pages
from app.rag.embedding import get_embedding_provider, tokenize
from app.rag.loader import extract_pages
from app.rag.vector_store import get_vector_store
from app.schemas.knowledge import SearchHit, SearchResponse


class KnowledgeService:
    async def index_document(
        self,
        session: AsyncSession,
        document_id: uuid.UUID,
    ) -> KnowledgeDocument:
        document = await session.get(KnowledgeDocument, document_id)
        if document is None:
            raise AppError(404, "NOT_FOUND", "文档不存在")

        document.status = "INDEXING"
        document.error_code = None
        await session.commit()
        vector_ids: list[str] = []
        try:
            content = Path(document.storage_path).read_bytes()
            pages = extract_pages(document.filename, content)
            chunks = chunk_pages(
                pages,
                chunk_size=settings.knowledge_chunk_size,
                overlap=settings.knowledge_chunk_overlap,
            )
            if not chunks:
                raise AppError(422, "DOCUMENT_EMPTY", "文档没有可索引文本")

            provider = get_embedding_provider()
            embeddings = await provider.embed_documents([chunk.content for chunk in chunks])
            records: list[KnowledgeChunk] = []
            for chunk in chunks:
                chunk_id = uuid.uuid4()
                vector_id = f"{document.id}:{document.index_version}:{chunk.index}"
                vector_ids.append(vector_id)
                records.append(
                    KnowledgeChunk(
                        id=chunk_id,
                        document_id=document.id,
                        chunk_index=chunk.index,
                        content=chunk.content,
                        page_number=chunk.page_number,
                        vector_id=vector_id,
                    )
                )
            session.add_all(records)
            await session.flush()
            await get_vector_store().upsert(
                ids=vector_ids,
                embeddings=embeddings,
                documents=[chunk.content for chunk in chunks],
                metadatas=[
                    {
                        "collection_id": str(document.collection_id),
                        "document_id": str(document.id),
                        "chunk_id": str(record.id),
                        "chunk_index": record.chunk_index,
                        "page_number": record.page_number or 0,
                    }
                    for record in records
                ],
            )
            document.status = "READY"
            await session.commit()
        except Exception as exc:
            await session.rollback()
            await get_vector_store().delete_ids(vector_ids)
            failed = await session.get(KnowledgeDocument, document_id)
            if failed is not None:
                failed.status = "FAILED"
                failed.error_code = _error_code(exc)
                await session.commit()
            if isinstance(exc, AppError):
                raise
            raise AppError(422, "DOCUMENT_INDEX_FAILED", "文档索引失败") from exc
        return await self.get_document(session, document_id)

    async def reindex_document(
        self,
        session: AsyncSession,
        document: KnowledgeDocument,
    ) -> KnowledgeDocument:
        if document.status == "DELETED":
            raise AppError(409, "STATE_CONFLICT", "已删除文档不能重建索引")
        await get_vector_store().delete_document(str(document.id))
        await session.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)
        )
        document.index_version += 1
        document.status = "PENDING"
        document.error_code = None
        await session.commit()
        return await self.index_document(session, document.id)

    async def delete_document(
        self,
        session: AsyncSession,
        document: KnowledgeDocument,
    ) -> KnowledgeDocument:
        document_id = document.id
        document.status = "DELETED"
        document.error_code = None
        await session.commit()
        try:
            await get_vector_store().delete_document(str(document.id))
            await session.execute(
                delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)
            )
            Path(document.storage_path).unlink(missing_ok=True)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            failed = await session.get(KnowledgeDocument, document.id)
            if failed is not None:
                failed.error_code = "DOCUMENT_DELETE_INCOMPLETE"
                await session.commit()
            raise AppError(503, "TOOL_UNAVAILABLE", "文档已隐藏，但索引清理尚未完成") from exc
        return await self.get_document(session, document_id)

    async def search(
        self,
        session: AsyncSession,
        collection_id: uuid.UUID,
        query: str,
        top_k: int,
    ) -> SearchResponse:
        provider = get_embedding_provider()
        embedding = await provider.embed_query(query)
        candidates = await get_vector_store().query(
            str(collection_id), embedding, max(top_k * 3, top_k)
        )
        vector_ids = [candidate["vector_id"] for candidate in candidates]
        if not vector_ids:
            return _empty_search(provider.source)

        rows = list(
            (
                await session.scalars(
                    select(KnowledgeChunk)
                    .join(KnowledgeDocument)
                    .where(
                        KnowledgeChunk.vector_id.in_(vector_ids),
                        KnowledgeDocument.collection_id == collection_id,
                        KnowledgeDocument.status == "READY",
                    )
                    .options(selectinload(KnowledgeChunk.document))
                )
            ).all()
        )
        chunks_by_vector = {chunk.vector_id: chunk for chunk in rows}
        hits: list[SearchHit] = []
        query_terms = set(tokenize(query))
        for candidate in candidates:
            chunk = chunks_by_vector.get(candidate["vector_id"])
            score = round(candidate["score"], 4)
            chunk_terms = set(tokenize(chunk.content)) if chunk is not None else set()
            if (
                chunk is None
                or score < settings.rag_min_score
                or not query_terms.intersection(chunk_terms)
            ):
                continue
            hits.append(
                SearchHit(
                    document_id=chunk.document_id,
                    filename=chunk.document.filename,
                    chunk_id=chunk.id,
                    page_number=chunk.page_number,
                    snippet=_snippet(chunk.content),
                    score=score,
                )
            )
            if len(hits) == top_k:
                break
        if not hits:
            return _empty_search(provider.source)
        first = hits[0]
        location = f"第 {first.page_number} 页" if first.page_number else ""
        answer = f"根据《{first.filename}》{location}：{first.snippet}"
        return SearchResponse(
            hits=hits,
            answer=answer,
            source=provider.source,
            has_sufficient_evidence=True,
        )

    async def get_document(
        self, session: AsyncSession, document_id: uuid.UUID
    ) -> KnowledgeDocument:
        document = await session.scalar(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.id == document_id)
            .options(
                selectinload(KnowledgeDocument.uploader),
                selectinload(KnowledgeDocument.chunks),
            )
        )
        if document is None:
            raise AppError(404, "NOT_FOUND", "文档不存在")
        return document


def _snippet(content: str, limit: int = 360) -> str:
    return content if len(content) <= limit else f"{content[:limit].rstrip()}…"


def _empty_search(source: str) -> SearchResponse:
    return SearchResponse(
        hits=[],
        answer="当前知识库未检索到足够依据。",
        source=source,
        has_sufficient_evidence=False,
    )


def _error_code(exc: Exception) -> str:
    if isinstance(exc, AppError):
        return exc.code
    if isinstance(exc, OSError):
        return "DOCUMENT_STORAGE_ERROR"
    return "DOCUMENT_INDEX_FAILED"


knowledge_service = KnowledgeService()
