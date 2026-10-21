from typing import Protocol

from app.schemas.chat import IntentParseResponse


class ModelProviderError(RuntimeError):
    pass


class LLMProvider(Protocol):
    async def extract_purchase_intent(self, text: str) -> IntentParseResponse: ...
