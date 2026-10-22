from typing import Any, Literal

from typing_extensions import TypedDict


class ApprovalStageState(TypedDict):
    stage: int
    task_id: str
    assignee_id: str
    approver_role: str


class GraphState(TypedDict):
    run_id: str
    purchase_request_id: str
    requester_id: str
    total_budget: str
    approval_stages: list[ApprovalStageState]
    current_stage_index: int
    current_stage: int | None
    pending_human_action: bool
    last_decision: dict[str, Any] | None
    status: Literal["RUNNING", "WAITING_APPROVAL", "APPROVED", "REJECTED"]
    errors: list[str]
    step_count: int
