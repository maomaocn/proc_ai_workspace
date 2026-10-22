import { flushPromises, mount } from "@vue/test-utils"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { api } from "../api/client"
import MCPToolsView from "./MCPToolsView.vue"

vi.mock("vue-router", () => ({
  useRoute: () => ({ params: {} }),
  useRouter: () => ({ replace: vi.fn() }),
}))

vi.mock("../api/client", () => ({
  ApiError: class ApiError extends Error {},
  api: {
    mcpServers: vi.fn(),
    mcpTools: vi.fn(),
    testMcpTool: vi.fn(),
  },
}))

const tool = {
  id: "mcp.inventory.search",
  server_name: "enterprise-ai-agent-hub-mcp",
  external_name: "inventory_search",
  description: "查询演示库存",
  input_schema: { type: "object" },
  output_schema: { type: "object" },
  allowed_roles: ["TECH_ADMIN" as const],
  read_only: true,
  enabled: true,
  timeout_ms: 5000,
  max_calls_per_run: 4,
}

describe("MCPToolsView", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.mcpServers).mockResolvedValue([{
      id: "server-1",
      name: "enterprise-ai-agent-hub-mcp",
      version: "1.30.0",
      transport: "stdio",
      config_ref: "app.mcp.server",
      enabled: true,
      health_status: "HEALTHY",
      last_checked_at: "2026-10-22T00:00:00Z",
      tool_count: 2,
      error_code: null,
    }])
    vi.mocked(api.mcpTools).mockResolvedValue([tool])
    vi.mocked(api.testMcpTool).mockResolvedValue({
      run: {
        id: "run-12345678",
        user_id: "user-1",
        username: "techadmin",
        request_id: null,
        graph_thread_id: null,
        run_type: "HARNESS",
        status: "SUCCEEDED",
        started_at: "2026-10-22T00:00:00Z",
        finished_at: "2026-10-22T00:00:01Z",
        duration_ms: 1000,
        error_code: null,
        model_provider: "mock",
        max_steps: 12,
        total_timeout_ms: 90000,
        step_count: 1,
        tool_call_count: 1,
        retry_count: 0,
      },
      output: { items: [] },
      source: "MCP_STDIO",
    })
  })

  it("runs only the selected registered tool with parsed JSON", async () => {
    const wrapper = mount(MCPToolsView, {
      global: { stubs: { RouterLink: true } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain("HEALTHY")
    expect(wrapper.text()).toContain("mcp.inventory.search")
    await wrapper.find("form").trigger("submit")
    await flushPromises()

    expect(api.testMcpTool).toHaveBeenCalledWith("mcp.inventory.search", {
      category: "笔记本电脑",
      min_qty: 1,
      limit: 5,
    })
    expect(wrapper.text()).toContain("运行成功")
  })
})
