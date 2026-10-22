from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel

from app.agent.state import GraphState


class ResumeDecision(BaseModel):
    decision_id: str
    task_id: str
    action: Literal["APPROVE", "REJECT"]
    actor_id: str
    comment: str | None = None


def resolve_approval_chain(state: GraphState) -> dict[str, object]:
    first = state["approval_stages"][0]
    return {
        "current_stage_index": 0,
        "current_stage": first["stage"],
        "pending_human_action": True,
        "status": "WAITING_APPROVAL",
        "step_count": state["step_count"] + 1,
    }


def await_approval(
    state: GraphState,
) -> Command[Literal["await_approval", "finalize", "record_rejection"]]:
    stage = state["approval_stages"][state["current_stage_index"]]
    raw_decision = interrupt(
        {
            "type": "approval",
            "run_id": state["run_id"],
            "purchase_request_id": state["purchase_request_id"],
            "stage": stage["stage"],
            "task_id": stage["task_id"],
            "approver_role": stage["approver_role"],
        }
    )
    decision = ResumeDecision.model_validate(raw_decision)
    if decision.task_id != stage["task_id"]:
        raise ValueError("resume task does not match the current approval stage")

    update: dict[str, object] = {
        "last_decision": decision.model_dump(),
        "pending_human_action": False,
        "step_count": state["step_count"] + 1,
    }
    if decision.action == "REJECT":
        return Command(update=update, goto="record_rejection")

    next_index = state["current_stage_index"] + 1
    if next_index < len(state["approval_stages"]):
        next_stage = state["approval_stages"][next_index]
        update.update(
            {
                "current_stage_index": next_index,
                "current_stage": next_stage["stage"],
                "pending_human_action": True,
                "status": "WAITING_APPROVAL",
            }
        )
        return Command(update=update, goto="await_approval")
    return Command(update=update, goto="finalize")


def finalize(state: GraphState) -> dict[str, object]:
    return {
        "current_stage": None,
        "pending_human_action": False,
        "status": "APPROVED",
        "step_count": state["step_count"] + 1,
    }


def record_rejection(state: GraphState) -> dict[str, object]:
    return {
        "current_stage": None,
        "pending_human_action": False,
        "status": "REJECTED",
        "step_count": state["step_count"] + 1,
    }


def build_approval_graph(checkpointer):
    builder = StateGraph(GraphState)
    builder.add_node("resolve_approval_chain", resolve_approval_chain)
    builder.add_node("await_approval", await_approval)
    builder.add_node("finalize", finalize)
    builder.add_node("record_rejection", record_rejection)
    builder.add_edge(START, "resolve_approval_chain")
    builder.add_edge("resolve_approval_chain", "await_approval")
    builder.add_edge("finalize", END)
    builder.add_edge("record_rejection", END)
    return builder.compile(checkpointer=checkpointer)
