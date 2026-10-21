import re
from decimal import Decimal

from app.llm.intents import build_intent_response
from app.schemas.chat import IntentParseResponse, PurchaseIntent

CATEGORY_KEYWORDS = {
    "笔记本电脑": ("笔记本", "电脑", "laptop"),
    "显示器": ("显示器", "屏幕", "monitor"),
    "办公椅": ("办公椅", "工学椅", "椅子"),
    "打印机": ("打印机", "printer"),
}


class MockLLMProvider:
    async def extract_purchase_intent(self, text: str) -> IntentParseResponse:
        normalized = " ".join(text.strip().split())
        category = next(
            (
                category
                for category, keywords in CATEGORY_KEYWORDS.items()
                if any(keyword.lower() in normalized.lower() for keyword in keywords)
            ),
            None,
        )
        quantity = self._first_int(
            normalized, r"(?:采购|购买|需要|申请)?\s*(\d+)\s*(?:台|个|件|套|把)"
        )
        unit_price = self._first_decimal(
            normalized,
            r"(?:每(?:台|个|件|套|把)|单价)(?:预算)?(?:不超过|不高于|上限(?:为)?|最多)?\s*(\d+(?:\.\d{1,2})?)\s*元?",
        )
        total_budget = self._first_decimal(
            normalized,
            r"总预算(?:不超过|不高于|上限(?:为)?|最多|是|为)?\s*(\d+(?:\.\d{1,2})?)\s*元?",
        )
        purpose_match = re.search(
            r"(?:用于|用途(?:是|为|[:：])?|使用场景(?:是|为|[:：])?)\s*([^，。；;]+)",
            normalized,
        )
        purpose = purpose_match.group(1).strip() if purpose_match else None
        priority = (
            "HIGH"
            if any(word in normalized for word in ("紧急", "加急", "尽快"))
            else "NORMAL"
        )

        intent = PurchaseIntent(
            category=category,
            item_description=category,
            quantity=quantity,
            unit_price_limit=unit_price,
            total_budget=total_budget,
            purpose=purpose,
            priority=priority,
        )
        return build_intent_response(intent, "MOCK")

    @staticmethod
    def _first_int(text: str, pattern: str) -> int | None:
        match = re.search(pattern, text, re.IGNORECASE)
        return int(match.group(1)) if match else None

    @staticmethod
    def _first_decimal(text: str, pattern: str) -> Decimal | None:
        match = re.search(pattern, text, re.IGNORECASE)
        return Decimal(match.group(1)) if match else None
