import { flushPromises, mount } from "@vue/test-utils"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { api } from "../api/client"
import type { Procurement } from "../api/types"
import { auth } from "../auth/store"
import ProcurementDetailView from "./ProcurementDetailView.vue"

vi.mock("vue-router", () => ({
  useRoute: () => ({ params: { requestId: "request-1" } }),
}))

vi.mock("../api/client", () => ({
  ApiError: class ApiError extends Error {},
  api: {
    procurement: vi.fn(),
    updateProcurement: vi.fn(),
    buildProcurementPlan: vi.fn(),
    approvalPreview: vi.fn(),
    submitProcurement: vi.fn(),
    cancelProcurement: vi.fn(),
    transitionFulfillment: vi.fn(),
  },
}))

const approved = {
  id: "request-1",
  requester_id: "employee-1",
  requester: { id: "employee-1", username: "employee" },
  title: "研发笔记本采购",
  category: "笔记本电脑",
  item_description: "研发办公笔记本",
  quantity: 10,
  unit_price_limit: "6000.00",
  total_budget: "60000.00",
  purpose: "研发办公",
  priority: "NORMAL",
  notes: null,
  status: "APPROVED",
  version: 3,
  linked_run_id: "run-1",
  candidates: [],
  approval_tasks: [],
  workflow_run: null,
  audit_events: [],
  created_at: "2026-10-22T00:00:00Z",
  updated_at: "2026-10-22T00:00:00Z",
} satisfies Procurement

describe("ProcurementDetailView fulfillment", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    auth.state.user = {
      id: "procurement-1",
      username: "procurement",
      department: { id: "department-1", name: "采购部" },
      roles: ["EMPLOYEE", "PROCUREMENT"],
      is_active: true,
      created_at: "2026-10-22T00:00:00Z",
    }
    auth.state.initialized = true
    vi.mocked(api.procurement)
      .mockResolvedValueOnce(approved)
      .mockResolvedValue({ ...approved, status: "ORDERED", version: 4 })
    vi.mocked(api.transitionFulfillment).mockResolvedValue({
      request_id: "request-1",
      previous_status: "APPROVED",
      purchase_status: "ORDERED",
      version: 4,
      audit_event_id: "audit-1",
      source: "DEMO",
      idempotent_replay: false,
    })
  })

  it("requires explicit confirmation and advances only to the next demo state", async () => {
    const wrapper = mount(ProcurementDetailView, {
      global: {
        stubs: {
          RouterLink: true,
          MoneyDisplay: true,
          SourceCitation: true,
          Teleport: true,
        },
      },
    })
    await flushPromises()

    expect(wrapper.text()).toContain("本地模拟状态")
    const open = wrapper.findAll("button").find(button => button.text().includes("确认模拟下单"))
    await open?.trigger("click")
    expect(api.transitionFulfillment).not.toHaveBeenCalled()

    const confirm = wrapper.findAll("button").find(
      button => button.text().includes("确认模拟操作"),
    )
    await confirm?.trigger("click")
    await flushPromises()

    expect(api.transitionFulfillment).toHaveBeenCalledTimes(1)
    expect(api.transitionFulfillment).toHaveBeenCalledWith(
      "request-1",
      "ORDERED",
      3,
      null,
      expect.stringMatching(/^[0-9a-f-]{36}$/),
    )
    expect(wrapper.text()).toContain("模拟履约状态已更新为 ORDERED")
  })
})
