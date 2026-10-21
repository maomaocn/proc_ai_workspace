import json
from decimal import Decimal

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.llm.mock import MockLLMProvider
from app.llm.openai_compatible import OpenAICompatibleLLMProvider
from app.schemas.chat import PurchaseIntent


@pytest.mark.asyncio
async def test_mock_parses_standard_purchase_intent_reproducibly() -> None:
    provider = MockLLMProvider()
    text = "采购10台笔记本，每台6000元，用于研发办公"

    first = await provider.extract_purchase_intent(text)
    second = await provider.extract_purchase_intent(text)

    assert first == second
    assert first.intent.category == "笔记本电脑"
    assert first.intent.quantity == 10
    assert first.intent.unit_price_limit == Decimal("6000")
    assert first.intent.total_budget == Decimal("60000.00")
    assert first.intent.purpose == "研发办公"
    assert first.missing_fields == []
    assert first.source == "MOCK"


@pytest.mark.asyncio
async def test_mock_requests_missing_purpose() -> None:
    result = await MockLLMProvider().extract_purchase_intent("采购10台笔记本，每台6000元")

    assert result.missing_fields == ["purpose"]
    assert result.follow_up_question == "请补充采购用途。"


def test_purchase_intent_rejects_invalid_quantity() -> None:
    with pytest.raises(ValidationError):
        PurchaseIntent(category="笔记本电脑", quantity=0)


@pytest.mark.asyncio
async def test_openai_compatible_repairs_one_invalid_response() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        content = "not json" if calls == 1 else json.dumps(
            {
                "category": "显示器",
                "item_description": "显示器",
                "quantity": 2,
                "unit_price_limit": "1500.00",
                "total_budget": None,
                "purpose": "设计工作",
                "priority": "NORMAL",
                "notes": None,
            }
        )
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = Settings(
        _env_file=None,
        model_provider="openai_compatible",
        openai_compatible_base_url="https://model.example/v1",
        openai_compatible_model="test-model",
    )
    provider = OpenAICompatibleLLMProvider(settings, client)
    try:
        result = await provider.extract_purchase_intent("采购两台显示器用于设计工作")
    finally:
        await client.aclose()

    assert calls == 2
    assert result.intent.total_budget == Decimal("3000.00")
    assert result.source == "OPENAI_COMPATIBLE"
