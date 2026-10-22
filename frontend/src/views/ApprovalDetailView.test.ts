import { flushPromises, mount } from "@vue/test-utils"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { api } from "../api/client"
import ApprovalDetailView from "./ApprovalDetailView.vue"

vi.mock("vue-router", () => ({
  useRoute: () => ({ params: { taskId: "task-1" } }),
}))

vi.mock("../api/client", () => ({
  ApiError: class ApiError extends Error {},
  api: {
    approvalTask: vi.fn(),
    decideApproval: vi.fn(),
  },
}))

const detail = {
  task: {
    id: "task-1",
    request_id: "request-1",
    stage: 1,
    approver_role: "APPROVER",
    assignee_id: "user-1",
    assignee: { id: "user-1", username: "manager" },
    status: "PENDING" as const,
    decision_comment: null,
    decided_at: null,
    created_at: "2026-10-22T00:00:00Z",
    updated_at: "2026-10-22T00:00:00Z",
    decisions: [],
  },
  procurement: {
    id: "request-1",
    requester_id: "employee-1",
    requester: { id: "employee-1", username: "employee" },
    title: "研发笔记本采购",
    category: "笔记本电脑",
    item_description: "开发设备",
    quantity: 2,
    unit_price_limit: "8000.00",
    total_budget: "16000.00",
    purpose: "研发",
    priority: "NORMAL" as const,
    notes: null,
    status: "PENDING_APPROVAL" as const,
    version: 2,
    linked_run_id: "run-1",
    candidates: [{
      id: "candidate-1",
      sku: "LAPTOP-001",
      model: "ThinkBook Demo",
      supplier_name: "演示供应商",
      quantity: 2,
      unit_price: "7000.00",
      total_price: "14000.00",
      source_type: "DEMO" as const,
    }],
    created_at: "2026-10-22T00:00:00Z",
    updated_at: "2026-10-22T00:00:00Z",
  },
  approval_chain: [],
}

describe("ApprovalDetailView", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.approvalTask).mockResolvedValue(detail)
    vi.mocked(api.decideApproval).mockResolvedValue({
      task_id: "task-1",
      task_status: "APPROVED",
      purchase_status: "PENDING_APPROVAL",
      decision_id: "decision-1",
      workflow_run_id: "run-1",
      next_task_id: "task-2",
      idempotent_replay: false,
    })
    vi.spyOn(window, "confirm").mockReturnValue(true)
  })

  it("requires a reason before rejecting", async () => {
    const wrapper = mount(ApprovalDetailView, {
      global: { stubs: { RouterLink: true, MoneyDisplay: true } },
    })
    await flushPromises()

    const reject = wrapper.findAll("button").find(button => button.text().includes("驳回"))
    await reject?.trigger("click")

    expect(wrapper.text()).toContain("驳回理由至少需要 5 个字符")
    expect(api.decideApproval).not.toHaveBeenCalled()
  })

  it("submits an approval once with a UUID idempotency key", async () => {
    const wrapper = mount(ApprovalDetailView, {
      global: { stubs: { RouterLink: true, MoneyDisplay: true } },
    })
    await flushPromises()

    const approve = wrapper.findAll("button").find(button => button.text().includes("批准"))
    await approve?.trigger("click")
    await flushPromises()

    expect(api.decideApproval).toHaveBeenCalledTimes(1)
    expect(api.decideApproval).toHaveBeenCalledWith(
      "task-1",
      { action: "APPROVE", comment: null },
      expect.stringMatching(/^[0-9a-f-]{36}$/),
    )
  })
})
