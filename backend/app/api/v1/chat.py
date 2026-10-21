import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DatabaseSession
from app.core.errors import AppError
from app.llm import LLMProvider, ModelProviderError, get_llm_provider
from app.llm.intents import FIELD_LABELS, REQUIRED_INTENT_FIELDS
from app.models.chat import ChatMessage, ChatSession
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageRead,
    ChatSessionCreate,
    ChatSessionRead,
    ChatSessionUpdate,
    ChatTurnResponse,
    IntentConfirmationRequest,
    IntentConfirmationResponse,
    IntentParseRequest,
    IntentParseResponse,
)
from app.schemas.common import Page

router = APIRouter(prefix="/chat", tags=["Chat"])
LLMDependency = Annotated[LLMProvider, Depends(get_llm_provider)]


async def owned_session(
    session_id: uuid.UUID, user_id: uuid.UUID, session: DatabaseSession
) -> ChatSession:
    chat_session = await session.get(ChatSession, session_id)
    if chat_session is None:
        raise AppError(404, "NOT_FOUND", "会话不存在")
    if chat_session.owner_id != user_id:
        raise AppError(403, "FORBIDDEN", "无权访问此会话")
    return chat_session


@router.get("/sessions", response_model=Page[ChatSessionRead])
async def list_sessions(
    user: CurrentUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    include_archived: bool = False,
) -> Page[ChatSessionRead]:
    filters = [ChatSession.owner_id == user.id]
    if not include_archived:
        filters.append(ChatSession.archived_at.is_(None))
    total = await session.scalar(
        select(func.count()).select_from(ChatSession).where(*filters)
    ) or 0
    query = (
        select(ChatSession)
        .where(*filters)
        .order_by(ChatSession.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list((await session.scalars(query)).all())
    return Page(items=items, page=page, page_size=page_size, total=total)


@router.post("/sessions", response_model=ChatSessionRead, status_code=201)
async def create_session(
    body: ChatSessionCreate, user: CurrentUser, session: DatabaseSession
) -> ChatSession:
    chat_session = ChatSession(owner_id=user.id, title=body.title.strip())
    session.add(chat_session)
    await session.commit()
    await session.refresh(chat_session)
    return chat_session


@router.get("/sessions/{session_id}", response_model=ChatSessionRead)
async def get_session_details(
    session_id: uuid.UUID, user: CurrentUser, session: DatabaseSession
) -> ChatSession:
    return await owned_session(session_id, user.id, session)


@router.patch("/sessions/{session_id}", response_model=ChatSessionRead)
async def update_session(
    session_id: uuid.UUID,
    body: ChatSessionUpdate,
    user: CurrentUser,
    session: DatabaseSession,
) -> ChatSession:
    chat_session = await owned_session(session_id, user.id, session)
    if body.title is not None:
        chat_session.title = body.title.strip()
    if body.archived is not None:
        chat_session.archived_at = datetime.now(UTC) if body.archived else None
    await session.commit()
    await session.refresh(chat_session)
    return chat_session


@router.get("/sessions/{session_id}/messages", response_model=Page[ChatMessageRead])
async def list_messages(
    session_id: uuid.UUID,
    user: CurrentUser,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Page[ChatMessageRead]:
    await owned_session(session_id, user.id, session)
    total = await session.scalar(
        select(func.count()).select_from(ChatMessage).where(ChatMessage.session_id == session_id)
    ) or 0
    query = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list((await session.scalars(query)).all())
    return Page(items=items, page=page, page_size=page_size, total=total)


@router.post("/parse-intent", response_model=IntentParseResponse)
async def parse_intent(
    body: IntentParseRequest,
    user: CurrentUser,
    session: DatabaseSession,
    provider: LLMDependency,
) -> IntentParseResponse:
    if body.session_id is not None:
        await owned_session(body.session_id, user.id, session)
    try:
        return await provider.extract_purchase_intent(body.text)
    except ModelProviderError as exc:
        raise AppError(503, "MODEL_UNAVAILABLE", "模型暂时无法解析采购需求") from exc


@router.post("/sessions/{session_id}/messages", response_model=ChatTurnResponse)
async def send_message(
    session_id: uuid.UUID,
    body: ChatMessageCreate,
    user: CurrentUser,
    session: DatabaseSession,
    provider: LLMDependency,
) -> ChatTurnResponse:
    chat_session = await owned_session(session_id, user.id, session)
    if chat_session.archived_at is not None:
        raise AppError(409, "STATE_CONFLICT", "归档会话不能继续发送消息")
    try:
        result = await provider.extract_purchase_intent(body.content)
    except ModelProviderError as exc:
        raise AppError(503, "MODEL_UNAVAILABLE", "模型暂时无法解析采购需求") from exc

    run_id = uuid.uuid4()
    user_message = ChatMessage(
        session_id=session_id,
        sender="USER",
        content=body.content,
        status="COMPLETED",
        run_id=run_id,
    )
    assistant_content = result.follow_up_question or (
        f"已整理 {result.intent.quantity} 项 {result.intent.category} 采购需求，请核对并确认。"
    )
    assistant_message = ChatMessage(
        session_id=session_id,
        sender="ASSISTANT",
        content=assistant_content,
        status="COMPLETED",
        run_id=run_id,
        payload_json=result.model_dump(mode="json"),
    )
    chat_session.updated_at = datetime.now(UTC)
    session.add_all([user_message, assistant_message])
    await session.commit()
    await session.refresh(user_message)
    await session.refresh(assistant_message)
    return ChatTurnResponse(
        run_id=run_id,
        user_message=ChatMessageRead.model_validate(user_message),
        assistant_message=ChatMessageRead.model_validate(assistant_message),
        parse_result=result,
    )


@router.post(
    "/messages/{message_id}/confirm-intent", response_model=IntentConfirmationResponse
)
async def confirm_intent(
    message_id: uuid.UUID,
    body: IntentConfirmationRequest,
    user: CurrentUser,
    session: DatabaseSession,
) -> IntentConfirmationResponse:
    message = await session.get(ChatMessage, message_id)
    if message is None:
        raise AppError(404, "NOT_FOUND", "消息不存在")
    chat_session = await session.get(ChatSession, message.session_id)
    if chat_session is None or chat_session.owner_id != user.id:
        raise AppError(403, "FORBIDDEN", "无权确认此采购意图")
    if message.sender != "ASSISTANT" or message.payload_json is None:
        raise AppError(409, "STATE_CONFLICT", "该消息不包含可确认的采购意图")

    missing = [field for field in REQUIRED_INTENT_FIELDS if getattr(body.intent, field) is None]
    if missing:
        labels = [FIELD_LABELS[field] for field in missing]
        raise AppError(
            422,
            "BUSINESS_RULE_VIOLATION",
            "采购意图仍有必填信息未补充",
            {"missing_fields": missing, "missing_labels": labels},
        )

    message.status = "CONFIRMED"
    message.payload_json = {
        **message.payload_json,
        "confirmed_intent": body.intent.model_dump(mode="json"),
        "confirmed_at": datetime.now(UTC).isoformat(),
    }
    chat_session.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(message)
    return IntentConfirmationResponse(
        message=ChatMessageRead.model_validate(message),
        confirmed_intent=body.intent,
    )
