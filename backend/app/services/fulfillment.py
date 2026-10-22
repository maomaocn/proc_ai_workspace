from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.approval import AuditEvent, IdempotencyRecord
from app.models.identity import User
from app.schemas.procurement import (
    FulfillmentTransitionRequest,
    FulfillmentTransitionResponse,
)
from app.services.procurement import procurement_service

NEXT_STATUS = {
    "APPROVED": "ORDERED",
    "ORDERED": "RECEIVED",
    "RECEIVED": "CLOSED",
}


def _payload_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


class FulfillmentService:
    async def transition(
        self,
        session: AsyncSession,
        purchase_id: uuid.UUID,
        body: FulfillmentTransitionRequest,
        idempotency_key: uuid.UUID,
        actor: User,
        request_id: uuid.UUID,
    ) -> FulfillmentTransitionResponse:
        operation = "procurement.fulfillment_transition"
        payload = {
            "request_id": str(purchase_id),
            "target_status": body.target_status,
            "version": body.version,
            "note": body.note,
        }
        request_hash = _payload_hash(payload)
        replay = await self._replay(
            session, actor.id, operation, idempotency_key, request_hash
        )
        if replay is not None:
            return replay

        # Recheck after locking: another transaction may have committed this key while we waited.
        purchase = await procurement_service.get(session, purchase_id, for_update=True)
        replay = await self._replay(
            session, actor.id, operation, idempotency_key, request_hash
        )
        if replay is not None:
            return replay
        if purchase.version != body.version:
            raise AppError(
                409,
                "STATE_CONFLICT",
                "采购申请已更新，请刷新后重试",
                {"current_version": purchase.version},
            )

        expected = NEXT_STATUS.get(purchase.status)
        if expected is None:
            raise AppError(
                409,
                "STATE_CONFLICT",
                "当前采购状态不允许继续履约",
                {"current_status": purchase.status},
            )
        if body.target_status != expected:
            raise AppError(
                409,
                "STATE_CONFLICT",
                "采购履约必须按顺序推进",
                {"current_status": purchase.status, "allowed_target": expected},
            )

        previous_status = purchase.status
        previous_version = purchase.version
        purchase.status = body.target_status
        purchase.version += 1
        audit = AuditEvent(
            actor_id=actor.id,
            action=f"FULFILLMENT_{body.target_status}",
            resource_type="PURCHASE_REQUEST",
            resource_id=purchase.id,
            before_json={"status": previous_status, "version": previous_version},
            after_json={
                "status": purchase.status,
                "version": purchase.version,
                "note": body.note,
                "source": "DEMO",
            },
            request_id=request_id,
        )
        session.add(audit)
        await session.flush()

        response = FulfillmentTransitionResponse(
            request_id=purchase.id,
            previous_status=previous_status,
            purchase_status=body.target_status,
            version=purchase.version,
            audit_event_id=audit.id,
        )
        session.add(
            IdempotencyRecord(
                actor_id=actor.id,
                operation=operation,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                resource_type="PURCHASE_REQUEST",
                resource_id=purchase.id,
                response_json=response.model_dump(mode="json"),
            )
        )
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            # The unique idempotency constraint selects a deterministic winner under concurrency.
            replay = await self._replay(
                session, actor.id, operation, idempotency_key, request_hash
            )
            if replay is not None:
                return replay
            raise AppError(409, "STATE_CONFLICT", "采购履约发生并发冲突") from exc
        return response

    async def _replay(
        self,
        session: AsyncSession,
        actor_id: uuid.UUID,
        operation: str,
        key: uuid.UUID,
        request_hash: str,
    ) -> FulfillmentTransitionResponse | None:
        record = await session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.actor_id == actor_id,
                IdempotencyRecord.operation == operation,
                IdempotencyRecord.idempotency_key == key,
            )
        )
        if record is None:
            return None
        if record.request_hash != request_hash:
            raise AppError(409, "IDEMPOTENCY_CONFLICT", "幂等键已用于不同的履约请求")
        payload = dict(record.response_json)
        payload["idempotent_replay"] = True
        return FulfillmentTransitionResponse.model_validate(payload)


fulfillment_service = FulfillmentService()
