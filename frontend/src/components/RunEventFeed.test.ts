import { mount } from "@vue/test-utils"
import { describe, expect, it } from "vitest"

import type { AgentEvent } from "../api/types"
import RunEventFeed from "./RunEventFeed.vue"

function event(seq: number, type: string, data: Partial<AgentEvent["data"]> = {}): AgentEvent {
  return {
    id: seq,
    event: type,
    data: {
      run_id: "run-1",
      seq,
      timestamp: "2026-10-22T00:00:00Z",
      ...data,
    },
  }
}

describe("RunEventFeed", () => {
  it("orders and deduplicates persisted stream events", () => {
    const wrapper = mount(RunEventFeed, {
      props: {
        events: [
          event(4, "run.completed"),
          event(2, "tool.started", { tool_name: "inventory.search" }),
          event(2, "tool.started", { tool_name: "inventory.search" }),
          event(3, "run.waiting_approval"),
          event(1, "message.delta"),
        ],
      },
    })

    expect(wrapper.findAll("li")).toHaveLength(4)
    expect(wrapper.text()).toContain("回复已接收")
    expect(wrapper.text()).toContain("工具 inventory.search 开始")
    expect(wrapper.text()).toContain("等待人工审批")
    expect(wrapper.text()).toContain("运行已完成")
  })
})
