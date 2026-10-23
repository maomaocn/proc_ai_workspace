from app.core.config import settings
from app.llm.base import LLMProvider
from app.llm.mock import MockLLMProvider
from app.llm.openai_compatible import OpenAICompatibleLLMProvider


def get_llm_provider() -> LLMProvider:
    # The API depends on this protocol-level factory, so Mock and remote modes do not change the
    # chat contract or any downstream procurement rule.
    if settings.model_provider == "openai_compatible":
        return OpenAICompatibleLLMProvider(settings)
    return MockLLMProvider()
