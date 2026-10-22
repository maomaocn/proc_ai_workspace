<script setup lang="ts">
import { ArrowRight, RefreshCw } from "@lucide/vue"
import { onMounted, ref, watch } from "vue"

import { api, ApiError } from "../api/client"
import type { AgentRunSummary } from "../api/types"

const runs = ref<AgentRunSummary[]>([])
const status = ref("")
const loading = ref(true)
const error = ref("")

async function load(): Promise<void> {
  loading.value = true
  error.value = ""
  const query = new URLSearchParams({ run_type: "HARNESS", page: "1", page_size: "100" })
  if (status.value) query.set("status", status.value)
  try {
    runs.value = (await api.agentRuns(query.toString())).items
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法读取 Harness 运行"
  } finally {
    loading.value = false
  }
}

watch(status, load)
onMounted(load)
</script>

<template>
  <div class="business-page technical-page">
    <header class="business-header">
      <div>
        <p class="overline">
          MINI AGENT HARNESS
        </p><h1>Harness 运行</h1><p>检查步数、工具调用、有限重试、超时和策略拒绝。</p>
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
        />刷新
      </button>
    </header>
    <div class="filter-bar technical-filter">
      <label><span>状态</span><select v-model="status"><option value="">全部状态</option><option>SUCCEEDED</option><option>FAILED</option><option>RUNNING</option></select></label>
    </div>
    <div
      v-if="error"
      class="inline-error"
      role="alert"
    >
      {{ error }}
    </div>
    <div
      v-else-if="loading"
      class="business-state"
    >
      正在读取运行记录...
    </div>
    <div
      v-else-if="runs.length === 0"
      class="business-state"
    >
      当前筛选下没有 Harness 运行。
    </div>
    <div
      v-else
      class="business-table-wrap"
    >
      <table class="business-table">
        <thead><tr><th>Run ID</th><th>用户</th><th>状态</th><th>步骤 / 工具</th><th>重试</th><th>错误码</th><th>耗时</th><th aria-label="操作" /></tr></thead><tbody>
          <tr
            v-for="run in runs"
            :key="run.id"
          >
            <td><strong>{{ run.id.slice(0, 8).toUpperCase() }}</strong><small>{{ new Date(run.started_at).toLocaleString("zh-CN", { hour12: false }) }}</small></td><td>{{ run.username }}</td><td><span :class="['status-badge', run.status.toLowerCase()]">{{ run.status }}</span></td><td>{{ run.step_count }} / {{ run.tool_call_count }}</td><td>{{ run.retry_count }}</td><td><code>{{ run.error_code || "-" }}</code></td><td>{{ run.duration_ms === null ? "运行中" : `${run.duration_ms} ms` }}</td><td>
              <RouterLink
                class="icon-link"
                :to="`/agent-runs/${run.id}`"
                title="查看运行步骤"
                aria-label="查看运行步骤"
              >
                <ArrowRight :size="17" />
              </RouterLink>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
