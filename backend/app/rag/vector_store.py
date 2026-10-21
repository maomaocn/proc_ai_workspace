import asyncio
from functools import lru_cache
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings


class ChromaVectorStore:
    def __init__(self, path: str, collection_name: str) -> None:
        client = chromadb.PersistentClient(
            path=path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine", "description": "Enterprise knowledge chunks"},
        )

    async def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, str | int]],
    ) -> None:
        await asyncio.to_thread(
            self.collection.upsert,
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    async def delete_document(self, document_id: str) -> None:
        await asyncio.to_thread(
            self.collection.delete,
            where={"document_id": {"$eq": document_id}},
        )

    async def delete_ids(self, ids: list[str]) -> None:
        if ids:
            await asyncio.to_thread(self.collection.delete, ids=ids)

    async def query(
        self,
        collection_id: str,
        embedding: list[float],
        top_k: int,
    ) -> list[dict[str, Any]]:
        result = await asyncio.to_thread(
            self.collection.query,
            query_embeddings=[embedding],
            n_results=top_k,
            where={"collection_id": {"$eq": collection_id}},
            include=["documents", "metadatas", "distances"],
        )
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        return [
            {
                "vector_id": vector_id,
                "document": document,
                "metadata": metadata,
                "score": max(0.0, min(1.0, 1.0 - float(distance))),
            }
            for vector_id, document, metadata, distance in zip(
                ids, documents, metadatas, distances, strict=True
            )
        ]


@lru_cache
def get_vector_store() -> ChromaVectorStore:
    return ChromaVectorStore(settings.chroma_path, settings.chroma_collection_name)
