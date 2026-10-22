<script setup lang="ts">
import { CheckCircle2, Play, RefreshCw, Server, ShieldCheck, Wrench } from "@lucide/vue"
import { computed, onMounted, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"

import { api, ApiError } from "../api/client"
import type { MCPServer, MCPTool, MCPToolTestResult } from "../api/types"

const route = useRoute()
const router = useRouter()
const servers = ref<MCPServer[]>([])
const tools = ref<MCPTool[]>([])
const selectedId = ref(String(route.params.toolId || ""))
const argumentsText = ref("")
const result = ref<MCPToolTestResult | null>(null)
const loading = ref(true)
const testing = ref(false)
const error = ref("")
const selected = computed(() => tools.value.find(tool => tool.id === selectedId.value) || tools.value[0])

function defaultArguments(tool: MCPTool | undefined): string {
  if (tool?.external_name === "supplier_quote") {
    return JSON.stringify({ item_id: "替换为库存 UUID", quantity: 10, limit: 5 }, null, 2)
  }
  return JSON.stringify({ category: "笔记本电脑", min_qty: 1, limit: 5 }, null, 2)
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ""
  try {
    ;[servers.value, tools.value] = await Promise.all([api.mcpServers(), api.mcpTools()])
    if (!selectedId.value && tools.value[0]) selectedId.value = tools.value[0].id
    argumentsText.value = defaultArguments(selected.value)
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法连接 MCP 工具中心"
  } finally {
    loading.value = false
  }
}

async function choose(tool: MCPTool): Promise<void> {
  selectedId.value = tool.id
  result.value = null
  await router.replace({ name: "mcp-tools", params: { toolId: tool.id } })
}

async function runTest(): Promise<void> {
  if (!selected.value) return
  testing.value = true
  error.value = ""
  result.value = null
  try {
    const args = JSON.parse(argumentsText.value) as Record<string, unknown>
    result.value = await api.testMcpTool(selected.value.id, args)
  } catch (caught) {
    error.value = caught instanceof SyntaxError
      ? "测试参数必须是合法 JSON。"
      : caught instanceof ApiError
        ? `${caught.message}（${caught.code}）`
        : "工具测试失败"
  } finally {
    testing.value = false
  }
}

watch(selected, tool => { argumentsText.value = defaultArguments(tool) })
onMounted(load)
</script>

<template>
  <div class="business-page technical-page">
    <header class="business-header">
      <div>
        <p class="overline">
          MODEL CONTEXT PROTOCOL
        </p><h1>MCP 工具中心</h1><p>发现受控 Server，仅试运行注册表中的只读白名单工具。</p>
      </div>
      <button
        class="secondary-button"
        type="button"
        :disabled="loading"
        @click="load"
      >
        <RefreshCw
          :size="16"
          :class="{ spinning: loading }"
        />重新检查
      </button>
    </header>
    <div
      v-if="error"
      class="inline-error"
      role="alert"
    >
      {{ error }}
    </div>
    <div
      v-if="loading"
      class="business-state"
    >
      正在握手并发现工具...
    </div>
    <template v-else>
      <section class="mcp-server-strip">
        <Server :size="22" /><div><small>SERVER</small><strong>{{ servers[0]?.name || "未配置" }}</strong><span>{{ servers[0]?.transport.toUpperCase() }} · SDK {{ servers[0]?.version || "未知" }}</span></div><span :class="['status-badge', servers[0]?.health_status.toLowerCase()]">{{ servers[0]?.health_status }}</span><span>{{ servers[0]?.tool_count || 0 }} TOOLS</span>
      </section>
      <div class="tool-center-layout">
        <section class="tool-catalog">
          <div class="panel-heading">
            <h2>已注册工具</h2><Wrench :size="18" />
          </div>
          <button
            v-for="tool in tools"
            :key="tool.id"
            type="button"
            :class="['tool-row', { selected: selected?.id === tool.id }]"
            @click="choose(tool)"
          >
            <span><strong>{{ tool.id }}</strong><small>{{ tool.external_name }} · {{ tool.timeout_ms }} ms</small></span><ShieldCheck :size="18" />
          </button>
        </section>
        <section
          v-if="selected"
          class="tool-inspector"
        >
          <div class="panel-heading">
            <div>
              <p class="overline">
                READ-ONLY TOOL
              </p><h2>{{ selected.id }}</h2>
            </div><span class="status-badge success">ENABLED</span>
          </div>
          <p class="tool-description">
            {{ selected.description }}
          </p>
          <dl class="technical-facts horizontal">
            <div><dt>Server</dt><dd>{{ selected.server_name }}</dd></div><div><dt>调用上限</dt><dd>{{ selected.max_calls_per_run }} / run</dd></div><div><dt>授权角色</dt><dd>{{ selected.allowed_roles.join(" · ") }}</dd></div>
          </dl>
          <details open>
            <summary>Input Schema</summary><pre>{{ JSON.stringify(selected.input_schema, null, 2) }}</pre>
          </details>
          <form
            class="tool-test-form"
            @submit.prevent="runTest"
          >
            <label><span>测试参数（JSON）</span><textarea
              v-model="argumentsText"
              rows="7"
              spellcheck="false"
            /></label><button
              class="primary-button"
              type="submit"
              :disabled="testing"
            >
              <Play :size="16" />{{ testing ? "执行中" : "运行只读测试" }}
            </button>
          </form>
          <div
            v-if="result"
            class="tool-result"
          >
            <div>
              <CheckCircle2 :size="18" /><strong>运行成功</strong><RouterLink :to="`/agent-runs/${result.run.id}`">
                RUN {{ result.run.id.slice(0, 8).toUpperCase() }}
              </RouterLink>
            </div><pre>{{ JSON.stringify(result.output, null, 2) }}</pre>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>
