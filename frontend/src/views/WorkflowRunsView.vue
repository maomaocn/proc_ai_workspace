<script setup lang="ts">
import { ArrowRight, GitBranch } from "@lucide/vue"
import { onMounted, ref } from "vue"

import { api, ApiError } from "../api/client"
import type { AgentRunSummary } from "../api/types"

const runs = ref<AgentRunSummary[]>([])
const loading = ref(true)
const error = ref("")

async function load(): Promise<void> {
  loading.value = true
  error.value = ""
  try {
    runs.value = (await api.agentRuns("run_type=WORKFLOW&page=1&page_size=100")).items
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法读取 Workflow 运行"
  } finally {
    loading.value = false
  }
}

function duration(run: AgentRunSummary): string {
  return run.duration_ms === null ? "等待中" : `${run.duration_ms} ms`
}

onMounted(load)
</script>

<template>
  <div class="business-page technical-page">
    <header class="business-header">
      <div>
        <p class="overline">
          LANGGRAPH OBSERVABILITY
        </p>
        <h1>Workflow 运行</h1>
        <p>按持久化步骤回看审批工作流的真实执行路径与暂停状态。</p>
      </div>
      <span class="source-chip">POSTGRES TRACE</span>
    </header>
    <div
      v-if="error"
      class="inline-error"
      role="alert"
    >
      {{ error }} <button
        class="text-button"
        type="button"
        @click="load"
      >
        重试
      </button>
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
      还没有 Workflow 运行记录。
    </div>
    <div
      v-else
      class="business-table-wrap"
    >
      <table class="business-table">
        <thead><tr><th>运行</th><th>业务单</th><th>发起人</th><th>状态</th><th>节点</th><th>耗时</th><th>开始时间</th><th aria-label="操作" /></tr></thead>
        <tbody>
          <tr
            v-for="run in runs"
            :key="run.id"
          >
            <td><span class="table-primary"><GitBranch :size="16" />{{ run.id.slice(0, 8).toUpperCase() }}</span><small>{{ run.graph_thread_id?.slice(0, 12) }}</small></td>
            <td>{{ run.request_id?.slice(0, 8).toUpperCase() || "-" }}</td>
            <td>{{ run.username }}</td>
            <td><span :class="['status-badge', run.status.toLowerCase()]">{{ run.status }}</span></td>
            <td>{{ run.step_count }}</td>
            <td>{{ duration(run) }}</td>
            <td>{{ new Date(run.started_at).toLocaleString("zh-CN", { hour12: false }) }}</td>
            <td>
              <RouterLink
                class="icon-link"
                :to="`/workflows/runs/${run.id}`"
                title="查看节点图"
                aria-label="查看节点图"
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
