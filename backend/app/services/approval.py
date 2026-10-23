import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent import workflow_runtime
from app.agent.state import ApprovalStageState, GraphState
from app.core.config import settings
from app.core.errors import AppError
from app.models.approval import (
    AgentRun,
    AgentStep,
    ApprovalDecision,
    ApprovalRule,
    ApprovalTask,
    AuditEvent,
    IdempotencyRecord,
    WorkflowResumeEvent,
)
from app.models.identity import Department, User, UserRole
from app.models.procurement import PurchaseCandidate, PurchaseRequest
from app.schemas.approval import (
    ApprovalCandidateRead,
    ApprovalDecisionCreate,
    ApprovalDecisionResponse,
    ApprovalPreview,
    ApprovalPreviewStage,
    ApprovalPurchaseRead,
    ApprovalRuleCreate,
    ApprovalRuleRead,
    ApprovalRuleUpdate,
    ApprovalTaskDetail,
    ApprovalTaskRead,
    ProcurementStateResponse,
    ProcurementSubmissionResponse,
    WorkflowRunRead,
)
from app.services.procurement import procurement_service


@dataclass(frozen=True)
class ResolvedStage:
    stage: int
    approver_role: str
    assignee: User


def _payload_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


class ApprovalService:
    async def preview(
        self, session: AsyncSession, purchase: PurchaseRequest, actor: User
    ) -> ApprovalPreview:
        procurement_service.require_owner_draft(purchase, actor)
        stages = await self._resolve_stages(session, purchase)
        return ApprovalPreview(
            request_id=purchase.id,
            total_budget=purchase.total_budget,
            stages=[
                ApprovalPreviewStage(
                    stage=item.stage,
                    approver_role=item.approver_role,
                    assignee_id=item.assignee.id,
                    assignee_username=item.assignee.username,
                    assignee_department=item.assignee.department.name,
                )
                for item in stages
            ],
        )

    async def submit(
        self,
        session: AsyncSession,
        purchase_id: uuid.UUID,
        version: int,
        idempotency_key: uuid.UUID,
        actor: User,
        request_id: uuid.UUID,
    ) -> ProcurementSubmissionResponse:
        operation = "procurement.submit"
        request_payload = {"request_id": str(purchase_id), "version": version}
        request_hash = _payload_hash(request_payload)
        replay = await self._submission_replay(
            session, actor.id, operation, idempotency_key, request_hash
        )
        if replay is not None:
            return replay

        purchase = await procurement_service.get(session, purchase_id, for_update=True)
        replay = await self._submission_replay(
            session, actor.id, operation, idempotency_key, request_hash
        )
        if replay is not None:
            return replay
        procurement_service.require_owner_draft(purchase, actor)
        if purchase.version != version:
            raise AppError(
                409,
                "STATE_CONFLICT",
                "采购草稿已被更新，请刷新后重试",
                {"current_version": purchase.version},
            )
        if not self._has_submittable_candidate(purchase):
            raise AppError(
                422,
                "BUSINESS_RULE_VIOLATION",
                "提交前必须生成至少一个库存充足且预算内的 DEMO 候选方案",
            )

        stages = await self._resolve_stages(session, purchase)
        now = datetime.now(UTC)
        run = AgentRun(
            user_id=actor.id,
            request_id=purchase.id,
            graph_thread_id=str(uuid.uuid4()),
            status="WAITING_APPROVAL",
            started_at=now,
            model_provider=settings.model_provider,
            steps=[],
        )
        session.add(run)
        await session.flush()

        tasks: list[ApprovalTask] = []
        for index, resolved in enumerate(stages):
            task = ApprovalTask(
                request=purchase,
                stage=resolved.stage,
                approver_role=resolved.approver_role,
                assignee=resolved.assignee,
                status="PENDING" if index == 0 else "WAITING",
                decisions=[],
            )
            session.add(task)
            tasks.append(task)
        await session.flush()

        before = {"status": purchase.status, "version": purchase.version}
        purchase.status = "PENDING_APPROVAL"
        purchase.version += 1
        purchase.linked_run_id = run.id
        run.steps.extend(
            [
                AgentStep(
                    step_index=0,
                    node_name="resolve_approval_chain",
                    status="SUCCEEDED",
                    started_at=now,
                    output_summary=f"resolved {len(tasks)} approval stage(s)",
                ),
                AgentStep(
                    step_index=1,
                    node_name=f"await_approval_stage_{tasks[0].stage}",
                    status="WAITING",
                    started_at=now,
                    input_summary=f"task_id={tasks[0].id}",
                ),
            ]
        )
        session.add(
            AuditEvent(
                actor_id=actor.id,
                action="PROCUREMENT_SUBMITTED",
                resource_type="PURCHASE_REQUEST",
                resource_id=purchase.id,
                before_json=before,
                after_json={"status": purchase.status, "version": purchase.version},
                request_id=request_id,
            )
        )

        graph_stages: list[ApprovalStageState] = [
            {
                "stage": task.stage,
                "task_id": str(task.id),
                "assignee_id": str(task.assignee_id),
                "approver_role": task.approver_role,
            }
            for task in tasks
        ]
        # Business rows remain authoritative. The graph receives serializable IDs and routing state
        # so it can pause/resume without duplicating purchase or approval records in its checkpoint.
        graph_state: GraphState = {
            "run_id": str(run.id),
            "purchase_request_id": str(purchase.id),
            "requester_id": str(actor.id),
            "total_budget": str(purchase.total_budget),
            "approval_stages": graph_stages,
            "current_stage_index": 0,
            "current_stage": None,
            "pending_human_action": False,
            "last_decision": None,
            "status": "RUNNING",
            "errors": [],
            "step_count": 0,
        }
        await workflow_runtime.begin(graph_state, run.graph_thread_id)
        await session.flush()

        response = ProcurementSubmissionResponse(
            request_id=purchase.id,
            purchase_status=purchase.status,
            version=purchase.version,
            run=WorkflowRunRead.model_validate(run),
            approval_tasks=[ApprovalTaskRead.model_validate(task) for task in tasks],
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
            replay = await self._submission_replay(
                session, actor.id, operation, idempotency_key, request_hash
            )
            if replay is not None:
                return replay
            raise AppError(409, "STATE_CONFLICT", "采购提交发生并发冲突") from exc
        return response

    async def cancel(
        self,
        session: AsyncSession,
        purchase_id: uuid.UUID,
        version: int,
        idempotency_key: uuid.UUID,
        actor: User,
        request_id: uuid.UUID,
    ) -> ProcurementStateResponse:
        operation = "procurement.cancel"
        payload = {"request_id": str(purchase_id), "version": version}
        request_hash = _payload_hash(payload)
        replay = await self._state_replay(
            session, actor.id, operation, idempotency_key, request_hash
        )
        if replay is not None:
            return replay

        purchase = await procurement_service.get(session, purchase_id, for_update=True)
        procurement_service.require_owner_draft(purchase, actor)
        if purchase.version != version:
            raise AppError(409, "STATE_CONFLICT", "采购草稿版本冲突")
        before = {"status": purchase.status, "version": purchase.version}
        purchase.status = "CANCELLED"
        purchase.version += 1
        response = ProcurementStateResponse(
            request_id=purchase.id,
            purchase_status=purchase.status,
            version=purchase.version,
        )
        session.add_all(
            [
                AuditEvent(
                    actor_id=actor.id,
                    action="PROCUREMENT_CANCELLED",
                    resource_type="PURCHASE_REQUEST",
                    resource_id=purchase.id,
                    before_json=before,
                    after_json={"status": purchase.status, "version": purchase.version},
                    request_id=request_id,
                ),
                IdempotencyRecord(
                    actor_id=actor.id,
                    operation=operation,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    resource_type="PURCHASE_REQUEST",
                    resource_id=purchase.id,
                    response_json=response.model_dump(mode="json"),
                ),
            ]
        )
        await session.commit()
        return response

    async def decide(
        self,
        session: AsyncSession,
        task_id: uuid.UUID,
        body: ApprovalDecisionCreate,
        idempotency_key: uuid.UUID,
        actor: User,
        request_id: uuid.UUID,
    ) -> ApprovalDecisionResponse:
        payload_hash = _payload_hash(
            {"task_id": str(task_id), "action": body.action, "comment": body.comment}
        )
        existing = await self._find_decision(session, actor.id, idempotency_key)
        if existing is not None:
            return await self._replay_decision(session, existing, payload_hash)

        task = await self._get_task(session, task_id, for_update=True)
        purchase = await procurement_service.get(session, task.request_id, for_update=True)
        existing = await self._find_decision(session, actor.id, idempotency_key)
        if existing is not None:
            return await self._replay_decision(session, existing, payload_hash)
        if purchase.requester_id == actor.id:
            raise AppError(403, "SELF_APPROVAL_FORBIDDEN", "申请人不能审批自己的采购申请")
        if task.assignee_id != actor.id:
            raise AppError(403, "FORBIDDEN", "只有当前任务的指定审批人可以操作")
        if task.status != "PENDING" or purchase.status != "PENDING_APPROVAL":
            raise AppError(409, "STATE_CONFLICT", "审批任务已处理或当前阶段尚未激活")

        now = datetime.now(UTC)
        before = {"purchase_status": purchase.status, "task_status": task.status}
        decision = ApprovalDecision(
            task=task,
            actor=actor,
            action=body.action,
            comment=body.comment,
            idempotency_key=idempotency_key,
            payload_hash=payload_hash,
        )
        session.add(decision)
        task.status = "APPROVED" if body.action == "APPROVE" else "REJECTED"
        task.decision_comment = body.comment
        task.decided_at = now

        next_task: ApprovalTask | None = None
        if body.action == "REJECT":
            purchase.status = "REJECTED"
            for pending in purchase.approval_tasks:
                if pending.status == "WAITING":
                    pending.status = "SKIPPED"
        else:
            next_task = next(
                (item for item in purchase.approval_tasks if item.status == "WAITING"), None
            )
            if next_task is None:
                purchase.status = "APPROVED"
            else:
                next_task.status = "PENDING"
        purchase.version += 1
        await session.flush()

        run = self._active_run(purchase)
        # Commit the decision and a durable resume event together. LangGraph is resumed only after
        # that transaction succeeds, so a transient graph failure can be replayed idempotently.
        event = WorkflowResumeEvent(
            run_id=run.id,
            decision_id=decision.id,
            status="PENDING",
            payload_json={
                "decision_id": str(decision.id),
                "task_id": str(task.id),
                "action": body.action,
                "actor_id": str(actor.id),
                "comment": body.comment,
            },
        )
        session.add_all(
            [
                event,
                AuditEvent(
                    actor_id=actor.id,
                    action=f"APPROVAL_{body.action}",
                    resource_type="PURCHASE_REQUEST",
                    resource_id=purchase.id,
                    before_json=before,
                    after_json={
                        "purchase_status": purchase.status,
                        "task_status": task.status,
                        "stage": task.stage,
                    },
                    request_id=request_id,
                ),
            ]
        )
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            existing = await self._find_decision(session, actor.id, idempotency_key)
            if existing is not None:
                return await self._replay_decision(session, existing, payload_hash)
            raise AppError(409, "STATE_CONFLICT", "审批任务发生并发冲突") from exc

        await self._process_resume_event(session, event.id)
        return ApprovalDecisionResponse(
            task_id=task.id,
            task_status=task.status,
            purchase_status=purchase.status,
            decision_id=decision.id,
            workflow_run_id=run.id,
            next_task_id=next_task.id if next_task else None,
        )

    async def task_detail(
        self, session: AsyncSession, task_id: uuid.UUID, actor: User
    ) -> ApprovalTaskDetail:
        task = await self._get_task(session, task_id)
        if task.assignee_id != actor.id:
            raise AppError(403, "FORBIDDEN", "无权查看此审批任务")
        purchase = await procurement_service.get(session, task.request_id)
        return ApprovalTaskDetail(
            task=ApprovalTaskRead.model_validate(task),
            procurement=self._approval_purchase(purchase),
            approval_chain=[
                ApprovalTaskRead.model_validate(item) for item in purchase.approval_tasks
            ],
        )

    async def list_rules(self, session: AsyncSession) -> list[ApprovalRuleRead]:
        rules = list(
            (
                await session.scalars(
                    select(ApprovalRule).order_by(ApprovalRule.min_amount, ApprovalRule.stage)
                )
            ).all()
        )
        return [ApprovalRuleRead.model_validate(item) for item in rules]

    async def create_rule(
        self, session: AsyncSession, body: ApprovalRuleCreate
    ) -> ApprovalRuleRead:
        await self._ensure_rule_no_overlap(session, body.model_dump())
        rule = ApprovalRule(**body.model_dump())
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return ApprovalRuleRead.model_validate(rule)

    async def update_rule(
        self, session: AsyncSession, rule_id: uuid.UUID, body: ApprovalRuleUpdate
    ) -> ApprovalRuleRead:
        rule = await session.get(ApprovalRule, rule_id)
        if rule is None:
            raise AppError(404, "NOT_FOUND", "审批规则不存在")
        values = body.model_dump(exclude_unset=True)
        proposed = {
            "min_amount": values.get("min_amount", rule.min_amount),
            "max_amount": values.get("max_amount", rule.max_amount),
            "stage": values.get("stage", rule.stage),
            "approver_role": values.get("approver_role", rule.approver_role),
            "active": values.get("active", rule.active),
        }
        if proposed["max_amount"] is not None and proposed["max_amount"] <= proposed["min_amount"]:
            raise AppError(422, "BUSINESS_RULE_VIOLATION", "审批规则金额区间无效")
        await self._ensure_rule_no_overlap(session, proposed, exclude_id=rule.id)
        for field, value in values.items():
            setattr(rule, field, value)
        await session.commit()
        await session.refresh(rule)
        return ApprovalRuleRead.model_validate(rule)

    async def _resolve_stages(
        self, session: AsyncSession, purchase: PurchaseRequest
    ) -> list[ResolvedStage]:
        amount = Decimal(purchase.total_budget)
        matching = list(
            (
                await session.scalars(
                    select(ApprovalRule)
                    .where(
                        ApprovalRule.active.is_(True),
                        ApprovalRule.min_amount <= amount,
                        or_(ApprovalRule.max_amount.is_(None), ApprovalRule.max_amount >= amount),
                    )
                    .order_by(ApprovalRule.stage)
                )
            ).all()
        )
        if not matching:
            raise AppError(
                422,
                "RULE_CONFIGURATION_MISSING",
                "当前金额没有可用审批规则，请联系管理员配置",
            )
        stages = [item.stage for item in matching]
        if len(stages) != len(set(stages)) or stages != list(range(1, max(stages) + 1)):
            raise AppError(
                422,
                "RULE_CONFIGURATION_INVALID",
                "审批规则存在重叠或级别缺口，请联系管理员修复",
            )

        assignees = list(
            (
                await session.scalars(
                    select(User)
                    .join(UserRole, UserRole.user_id == User.id)
                    .join(Department, Department.id == User.department_id)
                    .where(
                        User.is_active.is_(True),
                        UserRole.role == "APPROVER",
                        User.id != purchase.requester_id,
                    )
                    .options(selectinload(User.department), selectinload(User.role_assignments))
                    .order_by(User.username)
                )
            )
            .unique()
            .all()
        )
        resolved: list[ResolvedStage] = []
        selected_ids: set[uuid.UUID] = set()
        for rule in matching:
            candidates = [item for item in assignees if item.id not in selected_ids]
            if rule.stage == 1:
                preferred = [
                    item
                    for item in candidates
                    if item.department_id == purchase.requester.department_id
                ]
            else:
                preferred = [item for item in candidates if item.department.name == "财务部"]
            pool = preferred or candidates or assignees
            if not pool:
                raise AppError(
                    422,
                    "APPROVER_CONFIGURATION_MISSING",
                    f"第 {rule.stage} 级没有可用审批人",
                )
            assignee = pool[0]
            selected_ids.add(assignee.id)
            resolved.append(
                ResolvedStage(
                    stage=rule.stage,
                    approver_role=rule.approver_role,
                    assignee=assignee,
                )
            )
        return resolved

    def _has_submittable_candidate(self, purchase: PurchaseRequest) -> bool:
        return any(
            candidate.item.available_qty >= purchase.quantity
            and candidate.unit_price <= purchase.unit_price_limit
            and candidate.total_price <= purchase.total_budget
            for candidate in purchase.candidates
        )

    async def _submission_replay(
        self,
        session: AsyncSession,
        actor_id: uuid.UUID,
        operation: str,
        key: uuid.UUID,
        request_hash: str,
    ) -> ProcurementSubmissionResponse | None:
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
            raise AppError(409, "IDEMPOTENCY_CONFLICT", "幂等键已用于不同的提交请求")
        return ProcurementSubmissionResponse.model_validate(record.response_json)

    async def _state_replay(
        self,
        session: AsyncSession,
        actor_id: uuid.UUID,
        operation: str,
        key: uuid.UUID,
        request_hash: str,
    ) -> ProcurementStateResponse | None:
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
            raise AppError(409, "IDEMPOTENCY_CONFLICT", "幂等键已用于不同的取消请求")
        payload = dict(record.response_json)
        payload["idempotent_replay"] = True
        return ProcurementStateResponse.model_validate(payload)

    async def _find_decision(
        self, session: AsyncSession, actor_id: uuid.UUID, key: uuid.UUID
    ) -> ApprovalDecision | None:
        return await session.scalar(
            select(ApprovalDecision)
            .where(
                ApprovalDecision.actor_id == actor_id,
                ApprovalDecision.idempotency_key == key,
            )
            .options(
                selectinload(ApprovalDecision.task)
                .selectinload(ApprovalTask.request)
                .selectinload(PurchaseRequest.approval_tasks),
                selectinload(ApprovalDecision.task)
                .selectinload(ApprovalTask.request)
                .selectinload(PurchaseRequest.workflow_runs),
            )
        )

    async def _replay_decision(
        self,
        session: AsyncSession,
        decision: ApprovalDecision,
        payload_hash: str,
    ) -> ApprovalDecisionResponse:
        if decision.payload_hash != payload_hash:
            raise AppError(409, "IDEMPOTENCY_CONFLICT", "幂等键已用于不同的审批决定")
        event = await session.scalar(
            select(WorkflowResumeEvent).where(WorkflowResumeEvent.decision_id == decision.id)
        )
        if event is not None and event.status != "PROCESSED":
            await self._process_resume_event(session, event.id)
        task = decision.task
        purchase = await procurement_service.get(session, task.request_id)
        next_task = next(
            (item for item in purchase.approval_tasks if item.status == "PENDING"), None
        )
        run = self._active_run(purchase)
        return ApprovalDecisionResponse(
            task_id=task.id,
            task_status=task.status,
            purchase_status=purchase.status,
            decision_id=decision.id,
            workflow_run_id=run.id,
            next_task_id=next_task.id if next_task else None,
            idempotent_replay=True,
        )

    async def _get_task(
        self, session: AsyncSession, task_id: uuid.UUID, *, for_update: bool = False
    ) -> ApprovalTask:
        query = (
            select(ApprovalTask)
            .where(ApprovalTask.id == task_id)
            .execution_options(populate_existing=True)
            .options(
                selectinload(ApprovalTask.assignee),
                selectinload(ApprovalTask.decisions).selectinload(ApprovalDecision.actor),
                selectinload(ApprovalTask.request).selectinload(PurchaseRequest.requester),
                selectinload(ApprovalTask.request)
                .selectinload(PurchaseRequest.candidates)
                .selectinload(PurchaseCandidate.item),
                selectinload(ApprovalTask.request)
                .selectinload(PurchaseRequest.candidates)
                .selectinload(PurchaseCandidate.supplier),
                selectinload(ApprovalTask.request)
                .selectinload(PurchaseRequest.approval_tasks)
                .selectinload(ApprovalTask.assignee),
                selectinload(ApprovalTask.request)
                .selectinload(PurchaseRequest.approval_tasks)
                .selectinload(ApprovalTask.decisions)
                .selectinload(ApprovalDecision.actor),
                selectinload(ApprovalTask.request).selectinload(PurchaseRequest.workflow_runs),
            )
        )
        if for_update:
            query = query.with_for_update()
        task = await session.scalar(query)
        if task is None:
            raise AppError(404, "NOT_FOUND", "审批任务不存在")
        return task

    async def _process_resume_event(self, session: AsyncSession, event_id: uuid.UUID) -> None:
        """Resume checkpoint state from a durable, replayable business decision event."""

        event = await session.scalar(
            select(WorkflowResumeEvent).where(WorkflowResumeEvent.id == event_id)
        )
        if event is None or event.status == "PROCESSED":
            return
        run = await session.get(AgentRun, event.run_id)
        if run is None:
            raise AppError(500, "WORKFLOW_RUN_MISSING", "工作流运行记录不存在")
        try:
            snapshot = await workflow_runtime.resume(run.graph_thread_id, event.payload_json)
        except Exception as exc:
            event.status = "FAILED"
            event.error_code = "WORKFLOW_RESUME_FAILED"
            run.error_code = "WORKFLOW_RESUME_FAILED"
            await session.commit()
            raise AppError(
                503,
                "WORKFLOW_RESUME_PENDING",
                "审批决定已保存，但工作流恢复失败；使用相同幂等键重试",
                {"decision_id": str(event.decision_id)},
            ) from exc

        graph_status = snapshot["values"].get("status")
        event.status = "PROCESSED"
        event.processed_at = datetime.now(UTC)
        event.error_code = None
        run.error_code = None
        if graph_status == "WAITING_APPROVAL":
            run.status = "WAITING_APPROVAL"
        elif graph_status in {"APPROVED", "REJECTED"}:
            run.status = "SUCCEEDED"
            run.finished_at = datetime.now(UTC)
        else:
            run.status = "FAILED"
            run.error_code = "WORKFLOW_STATE_MISMATCH"
            await session.commit()
            raise AppError(503, "WORKFLOW_STATE_MISMATCH", "工作流状态与审批结果不一致")
        await self._append_resume_steps(session, run, event.payload_json, snapshot)
        await session.commit()

    async def _append_resume_steps(
        self,
        session: AsyncSession,
        run: AgentRun,
        payload: dict[str, Any],
        snapshot: dict[str, Any],
    ) -> None:
        max_index = await session.scalar(
            select(func.max(AgentStep.step_index)).where(AgentStep.run_id == run.id)
        )
        index = (max_index if max_index is not None else -1) + 1
        now = datetime.now(UTC)
        session.add(
            AgentStep(
                run_id=run.id,
                step_index=index,
                node_name=f"approval_stage_{payload.get('task_id')}",
                status="SUCCEEDED",
                started_at=now,
                input_summary=f"decision_id={payload.get('decision_id')}",
                output_summary=f"action={payload.get('action')}",
            )
        )
        graph_status = snapshot["values"].get("status")
        if graph_status == "WAITING_APPROVAL":
            session.add(
                AgentStep(
                    run_id=run.id,
                    step_index=index + 1,
                    node_name=f"await_approval_stage_{snapshot['values'].get('current_stage')}",
                    status="WAITING",
                    started_at=now,
                )
            )
        else:
            session.add(
                AgentStep(
                    run_id=run.id,
                    step_index=index + 1,
                    node_name="finalize" if graph_status == "APPROVED" else "record_rejection",
                    status="SUCCEEDED",
                    started_at=now,
                    output_summary=f"status={graph_status}",
                )
            )

    def _active_run(self, purchase: PurchaseRequest) -> AgentRun:
        if not purchase.workflow_runs:
            raise AppError(500, "WORKFLOW_RUN_MISSING", "采购申请缺少工作流运行记录")
        return purchase.workflow_runs[-1]

    def _approval_purchase(self, purchase: PurchaseRequest) -> ApprovalPurchaseRead:
        return ApprovalPurchaseRead(
            id=purchase.id,
            requester_id=purchase.requester_id,
            requester=purchase.requester,
            title=purchase.title,
            category=purchase.category,
            item_description=purchase.item_description,
            quantity=purchase.quantity,
            unit_price_limit=purchase.unit_price_limit,
            total_budget=purchase.total_budget,
            purpose=purchase.purpose,
            priority=purchase.priority,
            notes=purchase.notes,
            status=purchase.status,
            version=purchase.version,
            linked_run_id=purchase.linked_run_id,
            candidates=[
                ApprovalCandidateRead(
                    id=item.id,
                    sku=item.item.sku,
                    model=item.item.model,
                    supplier_name=item.supplier.name,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    total_price=item.total_price,
                )
                for item in purchase.candidates
            ],
            created_at=purchase.created_at,
            updated_at=purchase.updated_at,
        )

    async def _ensure_rule_no_overlap(
        self,
        session: AsyncSession,
        values: dict[str, Any],
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        if not values.get("active", True):
            return
        minimum = values["min_amount"]
        maximum = values.get("max_amount")
        filters = [
            ApprovalRule.active.is_(True),
            ApprovalRule.stage == values["stage"],
            or_(ApprovalRule.max_amount.is_(None), ApprovalRule.max_amount >= minimum),
        ]
        if maximum is not None:
            filters.append(ApprovalRule.min_amount <= maximum)
        if exclude_id is not None:
            filters.append(ApprovalRule.id != exclude_id)
        existing = await session.scalar(select(ApprovalRule.id).where(*filters).limit(1))
        if existing is not None:
            raise AppError(409, "RULE_RANGE_CONFLICT", "同一审批级别的有效金额区间不能重叠")


approval_service = ApprovalService()
