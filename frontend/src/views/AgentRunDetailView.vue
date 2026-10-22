<script setup lang="ts">
import { ArrowLeft, CheckCircle2, CircleAlert, Clock3 } from "@lucide/vue"
import { onMounted, ref } from "vue"
import { useRoute } from "vue-router"

import { api, ApiError } from "../api/client"
import type { AgentRunDetail } from "../api/types"

const route = useRoute()
const run = ref<AgentRunDetail | null>(null)
const loading = ref(true)
const error = ref("")

async function load(): Promise<void> {
  try {
    run.value = await api.agentRun(String(route.params.runId))
  } catch (caught) {
    error.value = caught instanceof ApiError ? caught.message : "无法读取运行详情"
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="business-page technical-page">
    <RouterLink
      class="back-link"
      to="/agent-runs"
    >
      <ArrowLeft :size="16" />返回 Harness 运行
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
      正在读取步骤...
    </div>
    <template v-else-if="run">
      <header class="business-header compact-header">
        <div>
          <p class="overline">
            RUN {{ run.id }}
          </p><h1>Harness 执行轨迹</h1><p>{{ run.username }} · {{ run.model_provider.toUpperCase() }} · 最大 {{ run.max_steps }} 步 / {{ run.total_timeout_ms }} ms</p>
        </div><span :class="['status-badge', run.status.toLowerCase()]">{{ run.status }}</span>
      </header>
      <section class="run-metrics">
        <div><span>执行步数</span><strong>{{ run.step_count }}</strong></div><div><span>工具调用</span><strong>{{ run.tool_call_count }}</strong></div><div><span>有限重试</span><strong>{{ run.retry_count }}</strong></div><div><span>总耗时</span><strong>{{ run.duration_ms === null ? "运行中" : `${run.duration_ms} ms` }}</strong></div><div><span>错误码</span><strong>{{ run.error_code || "无" }}</strong></div>
      </section>
      <ol class="run-timeline">
        <li
          v-for="step in run.steps"
          :key="step.id"
          :class="step.status.toLowerCase()"
        >
          <span class="timeline-icon"><CheckCircle2
            v-if="step.status === 'SUCCEEDED'"
            :size="18"
          /><CircleAlert
            v-else-if="step.status === 'FAILED'"
            :size="18"
          /><Clock3
            v-else
            :size="18"
          /></span><div>
            <div class="timeline-heading">
              <span><small>STEP {{ step.step_index + 1 }}</small><strong>{{ step.node_name }}</strong></span><span :class="['status-badge', step.status.toLowerCase()]">{{ step.status }}</span>
            </div><dl class="technical-facts horizontal">
              <div><dt>工具</dt><dd>{{ step.tool_name || "-" }}</dd></div><div><dt>耗时</dt><dd>{{ step.duration_ms === null ? "未提供" : `${step.duration_ms} ms` }}</dd></div><div><dt>错误码</dt><dd>{{ step.error_code || "无" }}</dd></div>
            </dl><details>
              <summary>查看脱敏输入 / 输出</summary><pre>INPUT  {{ step.input_summary || "未提供" }}

OUTPUT {{ step.output_summary || "未提供" }}</pre>
            </details>
          </div>
        </li>
      </ol>
    </template>
  </div>
</template>
