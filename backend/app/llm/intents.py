from app.schemas.chat import IntentParseResponse, PurchaseIntent

REQUIRED_INTENT_FIELDS = ("category", "quantity", "unit_price_limit", "purpose")
FIELD_LABELS = {
    "category": "采购品类",
    "quantity": "采购数量",
    "unit_price_limit": "单价预算上限",
    "purpose": "采购用途",
}


def build_intent_response(
    intent: PurchaseIntent, source: str
) -> IntentParseResponse:
    missing_fields = [
        field for field in REQUIRED_INTENT_FIELDS if getattr(intent, field) is None
    ]
    follow_up = None
    if missing_fields:
        labels = "、".join(FIELD_LABELS[field] for field in missing_fields)
        follow_up = f"请补充{labels}。"
    return IntentParseResponse(
        intent=intent,
        missing_fields=missing_fields,
        follow_up_question=follow_up,
        source=source,
    )
