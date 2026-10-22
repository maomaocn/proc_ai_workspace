<script setup lang="ts">
import { ArrowLeft, CheckCircle2, Circle, CircleAlert, Clock3 } from "@lucide/vue"
import { computed, onMounted, ref } from "vue"
import { useRoute } from "vue-router"

import { api, ApiError } from "../api/client"
import type { AgentStep, WorkflowRunDetail } from "../api/types"

const route = useRoute()
const detail = ref<WorkflowRunDetail | null>(null)
const selectedId = ref("")
const loading = ref(true)
const error = ref("")
const selected = computed(() => detail.value?.nodes.find(node => node.id === selectedId.value) || detail.value?.nodes[0])

function nodeIcon(status: string) {
  if (status === "SUCCEEDED") return CheckCircle2
  if (status === "FAILED") return CircleAlert
  if (status === "WAITING") return Clock3
  return Circle
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ""
  try {
    detail.value = await api.workflowRun(String(route.params.runId))
    selectedId.value = detail.value.nodes[0]?.id || ""
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法读取工作流运行"
  } finally {
    loading.value = false
  }
}

function summary(step: AgentStep | undefined): string {
  return step?.output_summary || step?.input_summary || "此节点没有记录摘要。"
}

onMounted(load)
</script>

<template>
  <div class="business-page technical-page">
    <RouterLink
      class="back-link"
      to="/workflows/runs"
    >
      <ArrowLeft :size="16" />返回运行列表
    </RouterLink>
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
      正在装载节点图...
    </div>
    <template v-else-if="detail">
      <header class="business-header compact-header">
        <div>
          <p class="overline">
            WORKFLOW RUN · {{ detail.run.id.slice(0, 8).toUpperCase() }}
          </p><h1>{{ detail.business_number || "审批工作流" }}</h1><p>{{ detail.run.graph_thread_id }} · {{ detail.run.username }}</p>
        </div>
        <span :class="['status-badge', detail.run.status.toLowerCase()]">{{ detail.run.status }}</span>
      </header>
      <div class="workflow-layout">
        <section
          class="workflow-canvas"
          aria-label="工作流节点图"
        >
          <button
            v-for="node in detail.nodes"
            :key="node.id"
            type="button"
            :class="['workflow-node', node.status.toLowerCase(), { selected: selected?.id === node.id }]"
            @click="selectedId = node.id"
          >
            <component
              :is="nodeIcon(node.status)"
              :size="19"
            />
            <span><small>STEP {{ node.step_index + 1 }}</small><strong>{{ node.node_name }}</strong><em>{{ node.status }}</em></span>
          </button>
        </section>
        <aside class="node-inspector">
          <p class="overline">
            NODE INSPECTOR
          </p><h2>{{ selected?.node_name }}</h2>
          <dl class="technical-facts">
            <div><dt>状态</dt><dd>{{ selected?.status }}</dd></div><div><dt>工具</dt><dd>{{ selected?.tool_name || "未调用" }}</dd></div><div><dt>耗时</dt><dd>{{ selected?.duration_ms === null ? "未提供" : `${selected?.duration_ms} ms` }}</dd></div><div><dt>错误码</dt><dd>{{ selected?.error_code || "无" }}</dd></div>
          </dl>
          <h3>脱敏摘要</h3><pre>{{ summary(selected) }}</pre>
        </aside>
      </div>
    </template>
  </div>
</template>
