from app.core.config import settings
from app.llm.base import LLMProvider
from app.llm.mock import MockLLMProvider
from app.llm.openai_compatible import OpenAICompatibleLLMProvider


def get_llm_provider() -> LLMProvider:
    if settings.model_provider == "openai_compatible":
        return OpenAICompatibleLLMProvider(settings)
    return MockLLMProvider()
