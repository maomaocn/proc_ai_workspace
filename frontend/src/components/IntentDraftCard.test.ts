import { mount, RouterLinkStub } from "@vue/test-utils"
import { describe, expect, it } from "vitest"

import type { ChatMessage } from "../api/types"
import IntentDraftCard from "./IntentDraftCard.vue"

function message(status: ChatMessage["status"] = "COMPLETED"): ChatMessage {
  return {
    id: "message-1",
    session_id: "session-1",
    sender: "ASSISTANT",
    content: "请补充采购用途。",
    status,
    run_id: "run-1",
    created_at: "2026-10-21T08:00:00Z",
    payload_json: {
      intent: {
        category: "笔记本电脑",
        item_description: "笔记本电脑",
        quantity: 10,
        unit_price_limit: "6000.00",
        total_budget: "60000.00",
        purpose: null,
        priority: "NORMAL",
        notes: null,
      },
      missing_fields: ["purpose"],
      follow_up_question: "请补充采购用途。",
      requires_confirmation: true,
      source: "MOCK",
    },
  }
}

describe("IntentDraftCard", () => {
  it("requires missing fields before emitting confirmation", async () => {
    const wrapper = mount(IntentDraftCard, { props: { message: message() } })

    await wrapper.get("form").trigger("submit")
    expect(wrapper.emitted("confirm")).toBeUndefined()
    expect(wrapper.text()).toContain("请填写采购用途")

    await wrapper.findAll("textarea")[0].setValue("研发办公")
    await wrapper.get("form").trigger("submit")

    const emitted = wrapper.emitted("confirm")
    expect(emitted).toHaveLength(1)
    expect(emitted?.[0]?.[0]).toMatchObject({
      quantity: 10,
      unit_price_limit: "6000.00",
      purpose: "研发办公",
    })
  })

  it("renders confirmed state with its procurement draft link", () => {
    const confirmed = message("CONFIRMED")
    if (confirmed.payload_json) {
      confirmed.payload_json.confirmed_intent = {
        ...confirmed.payload_json.intent,
        purpose: "研发办公",
      }
      confirmed.payload_json.purchase_request_id = "procurement-1"
    }
    const wrapper = mount(IntentDraftCard, {
      props: { message: confirmed },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })

    expect(wrapper.text()).toContain("已确认")
    expect(wrapper.text()).toContain("已创建采购草稿")
    expect(wrapper.getComponent(RouterLinkStub).props("to")).toBe(
      "/procurements/procurement-1",
    )
    expect(wrapper.find("button[type='submit']").exists()).toBe(false)
  })

  it("recalculates the read-only total when quantity or unit price changes", async () => {
    const wrapper = mount(IntentDraftCard, {
      props: { message: message() },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })
    const moneyInputs = wrapper.findAll("input[type='number']")

    await moneyInputs[1].setValue("9000")

    expect(moneyInputs[2].attributes("readonly")).toBeDefined()
    expect((moneyInputs[2].element as HTMLInputElement).value).toBe("90000.00")

    await wrapper.findAll("textarea")[0].setValue("研发办公")
    await wrapper.get("form").trigger("submit")
    expect(wrapper.emitted("confirm")?.[0]?.[0]).toMatchObject({
      unit_price_limit: "9000.00",
      total_budget: "90000.00",
    })
  })
})
