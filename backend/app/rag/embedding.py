import hashlib
import math
import re
from typing import Protocol

import httpx

from app.core.config import Settings, settings
from app.core.errors import AppError


class EmbeddingProvider(Protocol):
    source: str

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class MockHashEmbeddingProvider:
    """Deterministic lexical vectors for local tests, not a semantic language model."""

    source = "MOCK"

    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class RemoteEmbeddingProvider:
    source = "REMOTE"

    def __init__(self, config: Settings) -> None:
        self.base_url = config.remote_embedding_base_url.rstrip("/")
        self.api_key = config.remote_embedding_api_key
        self.model = config.remote_embedding_model
        self.timeout = config.embedding_request_timeout_seconds
        if not self.base_url or not self.model:
            raise AppError(503, "MODEL_UNAVAILABLE", "远程 Embedding 配置不完整")

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._request(texts)

    async def embed_query(self, text: str) -> list[float]:
        return (await self._request([text]))[0]

    async def _request(self, texts: list[str]) -> list[list[float]]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers=headers,
                    json={"model": self.model, "input": texts},
                )
                response.raise_for_status()
                data = response.json()["data"]
                ordered = sorted(data, key=lambda item: item["index"])
                embeddings = [item["embedding"] for item in ordered]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise AppError(503, "MODEL_UNAVAILABLE", "远程 Embedding 服务不可用") from exc
        if len(embeddings) != len(texts):
            raise AppError(503, "MODEL_UNAVAILABLE", "远程 Embedding 返回数量不匹配")
        return embeddings


def get_embedding_provider() -> EmbeddingProvider:
    # Indexing and querying both use this factory; changing providers therefore requires reindexing
    # existing documents so stored vectors keep the same dimensions and embedding space.
    if settings.embedding_provider == "remote":
        return RemoteEmbeddingProvider(settings)
    return MockHashEmbeddingProvider(settings.embedding_dimensions)


def tokenize(text: str) -> list[str]:
    normalized = text.lower()
    latin = re.findall(r"[a-z0-9]+", normalized)
    chinese = re.findall(r"[\u4e00-\u9fff]", normalized)
    bigrams = ["".join(chinese[index : index + 2]) for index in range(len(chinese) - 1)]
    return latin + (bigrams or chinese)
