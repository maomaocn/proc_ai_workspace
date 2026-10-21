import json
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.llm.base import ModelProviderError
from app.llm.intents import build_intent_response
from app.schemas.chat import IntentParseResponse, PurchaseIntent


class OpenAICompatibleLLMProvider:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client

    async def extract_purchase_intent(self, text: str) -> IntentParseResponse:
        if (
            not self.settings.openai_compatible_base_url
            or not self.settings.openai_compatible_model
        ):
            raise ModelProviderError("OpenAI-compatible provider is not configured")

        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "Extract only the user's procurement facts as JSON matching the supplied "
                    "schema. Use null for missing facts. Never invent vendors, stock, policy, "
                    "price, or purpose."
                ),
            },
            {"role": "user", "content": text},
        ]
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                payload = await self._request(messages)
                intent = PurchaseIntent.model_validate_json(payload)
                return build_intent_response(intent, "OPENAI_COMPATIBLE")
            except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
                last_error = exc
                if attempt == 0:
                    messages.append(
                        {
                            "role": "system",
                            "content": (
                                "The previous output was invalid. Return one valid JSON object "
                                "only."
                            ),
                        }
                    )
                    continue
                break
        raise ModelProviderError("Model returned an invalid purchase intent") from last_error

    async def _request(self, messages: list[dict[str, str]]) -> str:
        headers = {"Content-Type": "application/json"}
        if self.settings.openai_compatible_api_key:
            headers["Authorization"] = f"Bearer {self.settings.openai_compatible_api_key}"
        body: dict[str, Any] = {
            "model": self.settings.openai_compatible_model,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        url = f"{self.settings.openai_compatible_base_url.rstrip('/')}/chat/completions"
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(
            timeout=self.settings.model_request_timeout_seconds
        )
        try:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
            raise ModelProviderError("OpenAI-compatible model request failed") from exc
        finally:
            if owns_client:
                await client.aclose()
