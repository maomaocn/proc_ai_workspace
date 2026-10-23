from typing import Protocol

from app.schemas.chat import IntentParseResponse


class ModelProviderError(RuntimeError):
    pass


class LLMProvider(Protocol):
    """LLM adapter boundary.

    Providers may use deterministic local rules or a remote model, but callers always receive
    the same validated intent schema. Business writes never depend on an unvalidated model dict.
    """

    async def extract_purchase_intent(self, text: str) -> IntentParseResponse: ...
